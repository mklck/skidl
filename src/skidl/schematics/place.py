# -*- coding: utf-8 -*-

# The MIT License (MIT) - Copyright (c) 2016-2021 Dave Vandenbout.

"""
Autoplacer for arranging symbols in a schematic.
"""

from __future__ import (  # isort:skip
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import functools
import itertools
import math
import random
import sys
from builtins import range, zip
from collections import defaultdict, Counter
from copy import copy

from future import standard_library

from ..circuit import Circuit
from ..pin import Pin
from ..utilities import export_to_all, debug_trace, rmv_attr, sgn
from .debug_draw import draw_text, draw_end, draw_pause, draw_placement, draw_start, draw_redraw
from .geometry import BBox, Point, Tx, Vector

standard_library.install_aliases()

__all__ = [
    "PlacementFailure",
]


###################################################################
#
# OVERVIEW OF AUTOPLACER
#
# The input is a Node containing child nodes and parts. The parts in
# each child node are placed, and then the blocks for each child are
# placed along with the parts in this node.
#
# The individual parts in a node are separated into groups:
# 1) multiple groups of parts that are all interconnected by one or
# more nets, and 2) a single group of parts that are not connected
# by any explicit nets (i.e., floating parts).
#
# Each group of connected parts are placed using force-directed placement.
# Each net exerts an attractive force pulling parts together, and
# any overlap of parts exerts a repulsive force pushing them apart.
# Initially, the attractive force is dominant but, over time, it is
# decreased while the repulsive force is increased using a weighting
# factor. After that, any part overlaps are cleared and the parts
# are aligned to the routing grid.
#
# Force-directed placement is also used with the floating parts except
# the non-existent net forces are replaced by a measure of part similarity.
# This collects similar parts (such as bypass capacitors) together.
#
# The child-node blocks are then arranged with the blocks of connected
# and floating parts to arrive at a total placement for this node.
#
###################################################################


class PlacementFailure(Exception):
    """Exception raised when parts or blocks could not be placed."""

    pass


def get_snap_pt(part_or_blk):
    """Get the point for snapping the Part or PartBlock to the grid.

    Args:
        part_or_blk (Part | PartBlock): Object with snap point.

    Returns:
        Point: Point for snapping to grid or None if no point found.
    """
    try:
        return part_or_blk.pins[0].pt
    except AttributeError:
        try:
            return part_or_blk.snap_pt
        except AttributeError:
            return None


def snap_to_grid(part_or_blk):
    """Snap Part or PartBlock to grid.

    Args:
        part (Part | PartBlk): Object to snap to grid.
    """

    # Get the position of the current snap point.
    pt = get_snap_pt(part_or_blk) * part_or_blk.tx

    # This is where the snap point should be on the grid.
    snap_pt = pt.snap(GRID)

    # This is the required movement to get on-grid.
    mv = snap_pt - pt

    # Update the object's transformation matrix.
    snap_tx = Tx(dx=mv.x, dy=mv.y)
    part_or_blk.tx *= snap_tx


def add_placement_bboxes(parts, **options):
    """Expand part bounding boxes to include space for subsequent routing."""

    expansion_factor = options.get("expansion_factor", 1.0)
    for part in parts:

        # Placement bbox starts off with the part bbox (including any net labels).
        part.place_bbox = BBox()
        part.place_bbox.add(part.lbl_bbox)

        # Compute the routing area for each side based on the number of pins on each side.
        padding = {"U": 1, "D": 1, "L": 1, "R": 1}  # Min padding of 1 channel per side.
        for pin in part:
            if pin.stub is False and pin.is_connected():
                padding[pin.orientation] += 1

        # Add padding for routing to the right and upper sides.
        part.place_bbox.add(
            part.place_bbox.max
            + (Point(padding["L"], padding["D"]) * GRID * expansion_factor)
        )

        # Add padding for routing to the left and lower sides.
        part.place_bbox.add(
            part.place_bbox.min
            - (Point(padding["R"], padding["U"]) * GRID * expansion_factor)
        )


def add_anchor_pull_pins(parts, nets, **options):
    """Add positions of anchor and pull pins for attractive net forces between parts.

    Args:
        part (list): List of movable parts.
        nets (list): List of attractive nets between parts.
        options (dict): Dict of options and values that enable/disable functions.
    """
    from skidl.schematics.gen_schematic import NetTerminal

    def add_place_pt(part, pin):
        """Add the point for a pin on the placement boundary of a part."""

        pin.route_pt = pin.pt  # For drawing of nets during debugging.
        pin.place_pt = Point(pin.pt.x, pin.pt.y)
        if pin.orientation == "U":
            pin.place_pt.y = part.place_bbox.min.y
        elif pin.orientation == "D":
            pin.place_pt.y = part.place_bbox.max.y
        elif pin.orientation == "L":
            pin.place_pt.x = part.place_bbox.max.x
        elif pin.orientation == "R":
            pin.place_pt.x = part.place_bbox.min.x
        else:
            raise RuntimeError("Unknown pin orientation.")

    # Add dicts for anchor/pull pins and pin centroids to each movable part.
    for part in parts:
        part.anchor_pins = defaultdict(list)
        part.pull_pins = defaultdict(list)
        part.pin_ctrs = dict()

    if nets:
        # If nets exist, then these parts are interconnected so
        # assign pins on each net to part anchor and pull pin lists.
        for net in nets:

            # Get net pins that are on movable parts.
            pins = {pin for pin in net.pins if pin.part in parts}

            # Get the set of parts with pins on the net.
            net.parts = {pin.part for pin in pins}

            # Add each pin as an anchor on the part that contains it and
            # as a pull pin on all the other parts that will be pulled by this part.
            for pin in pins:
                pin.part.anchor_pins[net].append(pin)
                add_place_pt(pin.part, pin)
                for part in net.parts - {pin.part}:
                    # NetTerminals are pulled towards connected parts, but
                    # those parts are not attracted towards NetTerminals.
                    if not isinstance(pin.part, NetTerminal):
                        part.pull_pins[net].append(pin)

        # For each net, assign the centroid of the part's anchor pins for that net.
        pt_sum = functools.partial(sum, start=Point(0,0))
        for net in nets:
            for part in net.parts:
                if part.anchor_pins[net]:
                    part.pin_ctrs[net] = pt_sum(pin.place_pt for pin in part.anchor_pins[net]) / len(part.anchor_pins[net])

    else:
        # There are no nets so these parts are floating freely.
        # Floating parts are all pulled by each other.
        all_pull_pins = []
        for part in parts:
            try:
                # Set anchor at top-most pin so floating part tops will align.
                anchor_pull_pin = max(part.pins, key=lambda pin: pin.pt.y)
                add_place_pt(part, anchor_pull_pin)
            except ValueError:
                # Set anchor for part with no pins at all.
                anchor_pull_pin = Pin()
                anchor_pull_pin.place_pt = part.place_bbox.max
            part.anchor_pins["similarity"] = [anchor_pull_pin]
            part.pull_pins["similarity"] = all_pull_pins
            all_pull_pins.append(anchor_pull_pin)


def trim_anchor_pull_pins(parts):
    """Selectively remove anchor and pull pins from Part objects.

    Args:
        parts (list): List of movable parts.
    """

    if options.get("trim_anchor_pull_pins"):
        for part in parts:

            # Some nets attach to multiple pins on the same part. Trim the
            # anchor and pull pins for each net to a single pin for each part.

            # Only leave one randomly-chosen anchor point for a net on each part.
            anchor_pins = part.anchor_pins
            for net in anchor_pins.keys():
                anchor_pins[net] = [
                    random.choice(anchor_pins[net]),
                ]
            for net in anchor_pins.keys():
                assert len(anchor_pins[net]) == 1

            # Remove nets that have unusually large number of pulling points.
            # import statistics
            # fanouts = [len(pins) for pins in pull_pins.values()]
            # stdev = statistics.pstdev(fanouts)
            # avg = statistics.fmean(fanouts)
            # threshold = avg + 1*stdev
            # anchor_pins = {net: pins for net, pins in anchor_pins.items() if len(pull_pins[net]) <= threshold}
            # pull_pins = {net: pins for net, pins in pull_pins.items() if len(pins) <= threshold}

            # # Only leave one randomly-chosen pulling point for a net on each part.
            # for net, pins in pull_pins.items():
            #     part_pins = defaultdict(list)
            #     for pin in pins:
            #         part_pins[pin.part].append(pin)
            #     pull_pins[net].clear()
            #     for prt in part_pins.keys():
            #         pull_pins[net].append(random.choice(part_pins[prt]))
            # for net, pins in pull_pins.items():
            #     prts = [pin.part for pin in pins]
            #     assert len(prts) == len(set(prts))


def adjust_orientations(parts, **options):
    """Adjust orientation of parts.

    Args:
        parts (list): List of Parts to adjust.
        options (dict): Dict of options and values that enable/disable functions.

    Returns:
        bool: True if one or more part orientations were changed. Otherwise, False.
    """

    def find_best_orientation(part):
        # Each part has 8 possible orientations. Find the best of the 7 alternatives from the current one.

        # Store starting orientation and its cost.
        part.prev_tx = copy(part.tx)
        current_cost = net_tension(part, **options)

        # Now find the orientation that has the largest decrease in cost.
        best_delta_cost = float("inf")

        # Skip cost calculations for the starting orientation.
        skip_original_tx = True

        # Go through four rotations, then flip the part and go through the rotations again.
        for i in range(2):
            for j in range(4):

                if skip_original_tx:
                    # Skip the starting orientation but set flag to process the others.
                    skip_original_tx = False
                    delta_cost = 0

                else:
                    # Calculate the cost of the current orientation.
                    delta_cost = net_tension(part, **options) - current_cost
                    if delta_cost < best_delta_cost:
                        # Save the largest decrease in cost and the associated orientation.
                        best_delta_cost = delta_cost
                        best_tx = copy(part.tx)

                # Proceed to the next rotation.
                part.tx.rot_cw_90()

            # Flip the part and go through the rotations again.
            part.tx.flip_x()

        # Save the largest decrease in cost and the associated orientation.
        part.delta_cost = best_delta_cost
        part.delta_cost_tx = best_tx

        # Restore the original orientation.
        part.tx = part.prev_tx

    # Get the list of parts that don't have their orientations locked.
    movable_parts = [part for part in parts if not part.orientation_locked]

    if not movable_parts:
        # No movable parts, so exit without doing anything.
        return

    orientation_cost_history = []

    # Kernighan-Lin algorithm for finding near-optimal part orientations.
    # Because of the way the tension for part alignment is computed based on
    # the nearest part, it is possible for an infinite loop to occur.
    # Hence the ad-hoc loop limit.
    for iter_cnt in range(10):

        # Find the best part to move and move it until there are no more parts to move.
        moved_parts = []
        unmoved_parts = movable_parts[:]
        while unmoved_parts:

            # Find the best current orientation for each unmoved part.
            for part in unmoved_parts:
                find_best_orientation(part)

            # Find the part that has the largest decrease in cost.
            part_to_move = min(unmoved_parts, key=lambda p: p.delta_cost)

            # Reorient the part with the Tx that created the largest decrease in cost.
            part_to_move.tx = part_to_move.delta_cost_tx

            # Transfer the part from the unmoved to the moved part list.
            unmoved_parts.remove(part_to_move)
            moved_parts.append(part_to_move)

        # Find the point at which the cost reaches its lowest point.
        # delta_cost at location i is the change in cost *before* part i is moved.
        # Start with cost change of zero before any parts are moved.
        delta_costs = [0, ] # Start with delta cost for null move.
        delta_costs.extend((part.delta_cost for part in moved_parts))
        try:
            cost_seq = list(itertools.accumulate(delta_costs))
        except AttributeError:
            # Python 2.7 doesn't have itertools.accumulate().
            cost_seq = list(delta_costs)
            for i in range(1, len(cost_seq)):
                cost_seq[i] = cost_seq[i - 1] + cost_seq[i]
        min_cost = min(cost_seq)
        min_index = cost_seq.index(min_cost)

        # Move all the parts after that point back to their starting positions.
        for part in moved_parts[min_index:]:
            part.tx = part.prev_tx

        orientation_cost_history.append(min_cost)

        # Terminate the search if no part orientations were changed.
        if min_index == 0:
            break

    if options.get("show_orientation_cost"):
        import matplotlib.pyplot as plt

        plt.scatter(range(len(orientation_cost_history)), orientation_cost_history)
        plt.show()

    rmv_attr(parts, ("prev_tx", "delta_cost", "delta_cost_tx"))

    # Return True if one or more iterations were done, indicating part orientations were changed.
    return iter_cnt > 0


def net_tension_dist(part, **options):
    """Calculate the tension of the nets trying to rotate/flip the part.

    Args:
        part (Part): Part affected by forces from other connected parts.
        options (dict): Dict of options and values that enable/disable functions.

    Returns:
        float: Total tension on the part.
    """

    # Compute the force for each net attached to the part.
    tension = 0.0
    for net, anchor_pins in part.anchor_pins.items():

        pull_pins = part.pull_pins[net]

        if not anchor_pins or not pull_pins:
            # Skip nets without pulling or anchor points.
            continue

        # Compute the net force acting on each anchor point on the part.
        for anchor_pin in anchor_pins:

            # Compute the anchor point's (x,y).
            anchor_pt = anchor_pin.place_pt * anchor_pin.part.tx

            # Find the dist from the anchor point to each pulling point.
            dists = [
                (anchor_pt - pp.place_pt * pp.part.tx).magnitude for pp in pull_pins
            ]

            # Only the closest pulling point affects the tension since that is
            # probably where the wire routing will go to.
            tension += min(dists)

    return tension


def net_torque_dist(part, **options):
    """Calculate the torque of the nets trying to rotate/flip the part.

    Args:
        part (Part): Part affected by forces from other connected parts.
        options (dict): Dict of options and values that enable/disable functions.

    Returns:
        float: Total torque on the part.
    """

    # Part centroid for computing torque.
    ctr = part.place_bbox.ctr * part.tx

    # Get the force multiplier applied to point-to-point nets.
    pt_to_pt_mult = options.get("pt_to_pt_mult")

    # Compute the torque for each net attached to the part.
    torque = 0.0
    for net, anchor_pins in part.anchor_pins.items():

        pull_pins = part.pull_pins[net]

        if not anchor_pins or not pull_pins:
            # Skip nets without pulling or anchor points.
            continue

        pull_pin_pts = [pin.place_pt * pin.part.tx for pin in pull_pins]

        # Multiply the force exerted by point-to-point nets.
        force_mult = pt_to_pt_mult if len(pull_pin_pts)<=1 else 1

        # Compute the net torque acting on each anchor point on the part.
        for anchor_pin in anchor_pins:

            # Compute the anchor point's (x,y).
            anchor_pt = anchor_pin.place_pt * part.tx

            # Compute torque around part center from force between anchor & pull pins.
            normalize = len(pull_pin_pts)
            lever_norm = (anchor_pt - ctr).norm
            for pull_pt in pull_pin_pts:
                frc_norm = (pull_pt - anchor_pt).norm
                torque += lever_norm.xprod(frc_norm) * force_mult / normalize

    return abs(torque)


# Select the net tension method used for the adjusting the orientation of parts.
net_tension = net_tension_dist
# net_tension = net_torque_dist


@export_to_all
def net_force_dist(part, **options):
    """Compute attractive force on a part from all the other parts connected to it.

    Args:
        part (Part): Part affected by forces from other connected parts.
        options (dict): Dict of options and values that enable/disable functions.

    Returns:
        Vector: Force upon given part.
    """

    #
    # Various distance-to-force functions.
    #

    def dist_to_force_1(dist_vec):
        attenuation = 1
        max_, min_ = 4*GRID, 1*GRID
        dist_limit = 20 * GRID
        slope = (min_ - max_) / dist_limit
        dist = dist_vec.magnitude
        force = dist_vec.norm * max(slope * dist + max_, min_) * attenuation
        return force
    
    def dist_to_force_2(dist_vec):
        return dist_vec
    
    def dist_to_force_3(dist_vec):
        def rnd():
            return random.random() - 0.5
        dist_vec += Vector(GRID*rnd(), GRID*rnd())
        return dist_vec.norm * 5000 / dist_vec.magnitude
    
    def dist_to_force_4(dist_vec):
        return dist_vec.norm

    # Select the dist-to-force function to use.
    dist_to_force = dist_to_force_2

    # Get the anchor and pull pins for each net connected to this part.
    anchor_pins = part.anchor_pins
    pull_pins = part.pull_pins

    # Get the force multiplier applied to point-to-point nets.
    pt_to_pt_mult = options.get("pt_to_pt_mult")

    # Compute the total force on the part from all the anchor/pulling points on each net.
    total_force = Vector(0, 0)

    # Parts with a lot of pins can accumulate large net forces that move them very quickly.
    # Accumulate the number of individual net forces and use that to attenuate
    # the total force, effectively normalizing the forces between large & small parts.
    net_normalizer = 0

    # Compute the force for each net attached to the part.
    for net in anchor_pins.keys():

        if not anchor_pins[net] or not pull_pins[net]:
            # Skip nets without pulling or anchor points.
            continue

        # Multiply the force exerted by point-to-point nets.
        force_mult = pt_to_pt_mult if len(pull_pins[net])<=1 else 1

        # Initialize net force.
        net_force = Vector(0, 0)

        pin_normalizer = 0

        # Compute the anchor and pulling point (x,y)s for the net.
        anchor_pts = [pin.place_pt * pin.part.tx for pin in anchor_pins[net]]
        pull_pts = [pin.place_pt * pin.part.tx for pin in pull_pins[net]]

        # Compute the net force acting on each anchor point on the part.
        for anchor_pt in anchor_pts:

            # Sum the forces from each pulling point on the anchor point.
            for pull_pt in pull_pts:

                # Get the distance from the pull pt to the anchor point.
                dist_vec = pull_pt - anchor_pt

                # Add the force on the anchor pin from the pulling pin.
                net_force += dist_to_force(dist_vec)

                # Increment the normalizer for every pull force added to the net force.
                pin_normalizer += 1

        if options.get("normalize"):
            # Normalize the net force across all the anchor & pull pins.
            pin_normalizer = pin_normalizer or 1  # Prevent div-by-zero.
            net_force /= pin_normalizer

        # Accumulate force from this net into the total force on the part.
        # Multiply force if the net meets stated criteria.
        total_force += net_force * force_mult

        # Increment the normalizer for every net force added to the total force.
        net_normalizer += 1

    if options.get("normalize"):
        # Normalize the total force across all the nets.
        net_normalizer = net_normalizer or 1  # Prevent div-by-zero.
        total_force /= net_normalizer

    return total_force


@export_to_all
def net_force_dist_avg(part, **options):
    """Compute attractive force on a part from all the other parts connected to it.

    Args:
        part (Part): Part affected by forces from other connected parts.
        options (dict): Dict of options and values that enable/disable functions.

    Returns:
        Vector: Force upon given part.
    """

    # Notes:
    #     Computing net force proportional to distance between part pins
    #     can lead to highly-connected parts moving quickly and jumping over
    #     each other because of the total accumulated force. This can lead
    #     to a cascade where the parts actually start moving farther apart.
    #
    #     Limiting the movement of a part to the distance of its closest
    #     connection keeps the parts from jumping over each
    #     other, but can cause a problem if there are two or more clusters
    #     of parts on the same net in that parts in a cluster are attracted
    #     to each other, but the overall clusters are not attracted to each other.
    #
    #     A compromise is to limit the maximum pulling force for each net to
    #     be no more than the average distance from the anchor point to the pulling points.
    #     This seems to solve some of the problems of the first two techniques.

    anchor_pins = part.anchor_pins
    pull_pins = part.pull_pins

    # Get the force multiplier applied to point-to-point nets.
    pt_to_pt_mult = options.get("pt_to_pt_mult")

    # Compute the total force on the part from all the anchor/pulling points on each net.
    total_force = Vector(0, 0)

    # Parts with a lot of pins can accumulate large net forces that move them very quickly.
    # Accumulate the number of individual net forces and use that to attenuate
    # the total force, effectively normalizing the forces between large & small parts.
    net_normalizer = 0

    # Compute the force for each net attached to the part.
    for net in anchor_pins.keys():

        if not anchor_pins[net] or not pull_pins[net]:
            # Skip nets without pulling or anchor points.
            continue

        # Multiply the force exerted by point-to-point nets.
        force_mult = pt_to_pt_mult if len(pull_pins[net])<=1 else 1

        # Initialize net force.
        net_force = Vector(0, 0)

        # For averaging pin-to-pin distances.
        dist_sum = 0
        dist_cnt = 0

        # Compute the anchor and pulling point (x,y)s for the net.
        anchor_pts = [pin.place_pt * pin.part.tx for pin in anchor_pins[net]]
        pull_pts = [pin.place_pt * pin.part.tx for pin in pull_pins[net]]

        pin_normalizer = 0

        # Compute the net force acting on each anchor point on the part.
        for anchor_pt in anchor_pts:

            # Sum the forces from each pulling point on the anchor point.
            for pull_pt in pull_pts:

                # Get the distance from the pull pt to the anchor point.
                dist_vec = pull_pt - anchor_pt

                # Add the force on the anchor pin from the pulling pin.
                net_force += dist_vec

                # Update the values for computing the average distance.
                dist_sum += dist_vec.magnitude
                dist_cnt += 1

                pin_normalizer += 1

            if options.get("fanout_attenuation"):
                # Reduce the influence of high-fanout nets.
                fanout = len(pull_pins[net])
                net_force /= fanout**2

        if options.get("normalize"):
            # Normalize the net force across all the anchor & pull pins.
            pin_normalizer = pin_normalizer or 1  # Prevent div-by-zero.
            net_force /= pin_normalizer

        # Attenuate the net force if it's greater than the average distance btw anchor/pull pins.
        avg_dist = dist_sum / dist_cnt
        nt_frc_mag = net_force.magnitude
        if nt_frc_mag > avg_dist:
            net_force *= avg_dist / nt_frc_mag

        # Accumulate force from this net into the total force on the part.
        # Multiply force if the net meets stated criteria.
        total_force += net_force * force_mult

        # Increment the normalizer for every net force added to the total force.
        net_normalizer += 1

    if options.get("normalize"):
        # Normalize the total force to adjust for parts connected to a lot of nets.
        net_normalizer = net_normalizer or 1  # Prevent div-by-zero.
        total_force /= net_normalizer

    return total_force


@export_to_all
def net_force_bbox(part, **options):
    """Compute attractive force on a part from all the other parts connected to it.

    Args:
        part (Part): Part affected by forces from other connected parts.
        options (dict): Dict of options and values that enable/disable functions.

    Returns:
        Vector: Force upon given part.
    """

    anchor_pins = part.anchor_pins
    pull_pins = part.pull_pins

    # Storage for the change in cost for each orthogonal movement.
    cost_chg = {Vector(1,0):0, Vector(-1,0):0, Vector(0,1):0, Vector(0,-1):0}

    # Compute the force for each net attached to the part.
    for net in anchor_pins.keys():

        if not anchor_pins[net] or not pull_pins[net]:
            # Skip nets without pulling or anchor points.
            continue

        # Function for summing points to find their centroid.
        pt_sum = functools.partial(sum, start=Point(0,0))

        # Find the bounding box for the anchor points and their centroid.
        anchor_pts = [pin.place_pt * pin.part.tx for pin in anchor_pins[net]]
        anchor_bbox = BBox(*anchor_pts)
        anchor_ctr = pt_sum(anchor_pts) / len(anchor_pts)

        # Find the bounding box for the pulling points and their centroid.
        pull_pts = [pin.place_pt * pin.part.tx for pin in pull_pins[net]]
        pull_bbox = BBox(*pull_pts)
        pull_ctr = pt_sum(pull_pts) / len(pull_pts)

        # Get the distance between the anchor and pulling point centroids.
        # We want to make this smaller.
        dist = (anchor_ctr - pull_ctr).magnitude

        # Get the total bounding box around all the anchor and pulling points.
        # We want to make the height, width of this bounding box smaller.
        total_bbox = anchor_bbox + pull_bbox
        hw = total_bbox.h + total_bbox.w

        # Test each direction to see which one makes the cost smaller.
        for dir in cost_chg:
            # Move the part which will move the bounding box and centroid of the anchor points.
            tx = Tx(dx=dir.x, dy=dir.y)
            bbx = anchor_bbox * tx + pull_bbox
            # Compute the change in bounding box dimensions and dis between anchor/pull centroids.
            hw_chg = (bbx.h + bbx.w) - hw
            dist_chg = (anchor_ctr * tx - pull_ctr).magnitude - dist
            cost_chg[dir] += hw_chg + dist_chg

    # Find the direction that decreases cost the most.
    best_dir, best_chg = min(cost_chg.items(), key=lambda x: x[1])
    if best_chg > 0:
        # Cost didn't go down, so don't move in any direction.
        best_dir = Vector(0,0)

    return best_dir


@export_to_all
def net_force_centroid(part, **options):
    """Compute attractive force on a part from all the other parts connected to it.

    Args:
        part (Part): Part affected by forces from other connected parts.
        options (dict): Dict of options and values that enable/disable functions.

    Returns:
        Vector: Force upon given part.

    Note:
        If a net attaches to multiple pins of a part, then this function uses
        the centroid of those pins as the point at which the attractive forces
        is exerted.
    """

    from skidl.schematics.gen_schematic import NetTerminal

    fanout_attenuation = options.get("fanout_attenuation")

    # Compute and sum the forces for all nets attached to the part.
    total_force = Vector(0, 0)
    net_normalizer = 0
    for net, anchor_ctr in part.pin_ctrs.items():

        # Massively reduce the forces from "high-fanout" nets.
        force_attenuation = 1.0
        if fanout_attenuation:
            part_fanout = len(net.parts)
            if part_fanout > 3:
                force_attenuation = 0.01

        # Find the translated centroid for the anchor pins of the net on this part.
        anchor_ctr *= part.tx

        # Find the centroid for the pulling points of the other parts connected to this net.
        for pull_part in net.parts - {part}:

            # Skip NetTerminals because they cannot exert forces on other parts.
            if isinstance(pull_part, NetTerminal):
                continue

            # Get the translated centroid of the pin pulling from the other part.
            pull_ctr = pull_part.pin_ctrs[net] * pull_part.tx

            # Add the distance between the anchor and pulling centroids to the total force on the part.
            total_force += (pull_ctr - anchor_ctr) * force_attenuation

        # Keep track of the number of nets that exert forces in case normalization is needed.
        net_normalizer += 1

    if options.get("normalize"):
        # Normalize the total force to adjust for parts connected to a lot of nets.
        net_normalizer = net_normalizer or 1  # Prevent div-by-zero.
        total_force /= net_normalizer

    return total_force


# Select the net force method used for the attraction of parts during placement.
# attractive_force = net_force_dist
# attractive_force = net_force_dist_avg
# attractive_force = net_force_bbox
# attractive_force = net_force_centroid


@export_to_all
def overlap_force(part, parts, **options):
    """Compute the repulsive force on a part from overlapping other parts.

    Args:
        part (Part): Part affected by forces from other overlapping parts.
        parts (list): List of parts to check for overlaps.
        options (dict): Dict of options and values that enable/disable functions.

    Returns:
        Vector: Force upon given part.
    """

    def rand_offset():
        return Point(random.random() - 0.5, random.random() - 0.5)

    # Bounding box of given part.
    part_bbox = part.place_bbox * part.tx

    # Compute the overlap force of the bbox of this part with every other part.
    total_force = Vector(0, 0)
    for other_part in set(parts) - {part}:

        other_part_bbox = other_part.place_bbox * other_part.tx

        # No force unless parts overlap.
        if part_bbox.intersects(other_part_bbox):

            # Compute the movement needed to clear the bboxes in left/right/up/down directions.
            # Add some small random offset to break symmetry when parts exactly overlay each other.
            # Move right edge of part to the left of other part's left edge.
            mv_left = other_part_bbox.ll - part_bbox.lr + rand_offset()
            # Move left edge of part to the right of other part's right edge.
            mv_right = other_part_bbox.lr - part_bbox.ll + rand_offset()
            # Move bottom edge of part above other part's upper edge.
            mv_up = other_part_bbox.ul - part_bbox.ll + rand_offset()
            # Move upper edge of part below other part's bottom edge.
            mv_down = other_part_bbox.ll - part_bbox.ul + rand_offset()

            # Find the minimal movements in the left/right and up/down directions.
            mv_lr = mv_left if abs(mv_left.x) < abs(mv_right.x) else mv_right
            mv_ud = mv_up if abs(mv_up.y) < abs(mv_down.y) else mv_down

            # Remove any orthogonal component of the left/right and up/down movements.
            mv_lr.y = 0  # Remove up/down component.
            mv_ud.x = 0  # Remove left/right component.

            # Pick the smaller of the left/right and up/down movements because that will
            # cause movement in the direction that will clear the overlap most quickly.
            mv = mv_lr if abs(mv_lr.x) < abs(mv_ud.y) else mv_ud

            # Add movement for this part overlap to the total force.
            total_force += mv

    return total_force


# Select the overlap force method used for the repulsion of parts during placement.
repulsive_force = overlap_force


def scale_attractive_repulsive_forces(parts, force_func, **options):
    """Set scaling between attractive net forces and repulsive part overlap forces."""

    # Store original part placement.
    for part in parts:
        part.original_tx = copy(part.tx)

    # Find attractive forces when they are maximized by random part placement.
    random_placement(parts, **options)
    attractive_forces_sum = sum(force_func(p, parts, alpha=0, scale=1, **options).magnitude for p in parts)

    # Find repulsive forces when they are maximized by compacted part placement.
    central_placement(parts, **options)
    repulsive_forces_sum = sum(force_func(p, parts, alpha=1, scale=1, **options).magnitude for p in parts)

    # Restore original part placement.
    for part in parts:
        part.tx = part.original_tx
    rmv_attr(parts, ["original_tx"])

    # Return scaling factor that makes attractive forces about the same as repulsive forces.
    return repulsive_forces_sum / attractive_forces_sum


def total_part_force(part, parts, scale, alpha, **options):
    """Compute the total of the attractive net and repulsive overlap forces on a part.

    Args:
        part (Part): Part affected by forces from other overlapping parts.
        parts (list): List of parts to check for overlaps.
        scale (float): Scaling factor for net forces to make them equivalent to overlap forces.
        alpha (float): Fraction of the total that is the overlap force (range [0,1]).
        options (dict): Dict of options and values that enable/disable functions.

    Returns:
        Vector: Weighted total of net attractive and overlap repulsion forces.
    """
    force = scale * (1-alpha) * attractive_force(part, **options) + alpha * repulsive_force(part, parts, **options)
    part.force = force  # For debug drawing.
    return force


def similarity_force(part, parts, similarity, **options):
    """Compute attractive force on a part from all the other parts connected to it.

    Args:
        part (Part): Part affected by similarity forces with other parts.
        similarity (dict): Similarity score for any pair of parts used as keys.
        options (dict): Dict of options and values that enable/disable functions.

    Returns:
        Vector: Force upon given part.
    """

    # Get the single anchor point for similarity forces affecting this part.
    anchor_pt = part.anchor_pins["similarity"][0].place_pt * part.tx

    # Compute the combined force of all the similarity pulling points.
    total_force = Vector(0, 0)
    for pull_pin in part.pull_pins["similarity"]:
        pull_pt = pull_pin.place_pt * pull_pin.part.tx
        # Force from pulling to anchor point is proportional to part similarity and distance.
        total_force += (pull_pt - anchor_pt) * similarity[part][pull_pin.part]

    return total_force


def total_similarity_force(part, parts, similarity, scale, alpha, **options):
    """Compute the total of the attractive similarity and repulsive overlap forces on a part.

    Args:
        part (Part): Part affected by forces from other overlapping parts.
        parts (list): List of parts to check for overlaps.
        similarity (dict): Similarity score for any pair of parts used as keys.
        scale (float): Scaling factor for similarity forces to make them equivalent to overlap forces.
        alpha (float): Proportion of the total that is the overlap force (range [0,1]).
        options (dict): Dict of options and values that enable/disable functions.

    Returns:
        Vector: Weighted total of net attractive and overlap repulsion forces.
    """
    force = scale * (1-alpha)*similarity_force(part, parts, similarity, **options) + alpha * repulsive_force(part, parts, **options)
    part.force = force  # For debug drawing.
    return force


@debug_trace
def central_placement(parts, **options):
    """Cluster all part centroids onto a common point.

    Args:
        parts (list): List of Parts.
        options (dict): Dict of options and values that enable/disable functions.
    """

    if len(parts) <= 1:
        # No need to do placement if there's less than two parts.
        return

    # Find the centroid of all the parts.
    bbox = BBox()
    for part in parts:
        bbox.add(part.place_bbox * part.tx)
    ctr = bbox.ctr

    # Collapse all the parts to the centroid.
    for part in parts:
        mv = ctr - part.place_bbox.ctr * part.tx
        part.tx *= Tx(dx=mv.x, dy=mv.y)


def define_placement_bbox(parts, **options):
    """Return a bounding box big enough to hold the parts being placed."""

    # Compute appropriate size to hold the parts based on their areas.
    area = 0
    for part in parts:
        area += part.place_bbox.area
    side = 3 * math.sqrt(area)  # FIXME: Multiplier is ad-hoc.
    return BBox(Point(0,0), Point(side, side))


@debug_trace
def random_placement(parts, **options):
    """Randomly place parts within an appropriately-sized area.

    Args:
        parts (list): List of Parts to place.
    """

    # Compute appropriate size to hold the parts based on their areas.
    bbox = define_placement_bbox(parts, **options)

    # Place parts randomly within area.
    for part in parts:
        pt = Point(random.random() * bbox.w, random.random() * bbox.h)
        part.tx.move_to(pt)
        # The following setter doesn't work in Python 2.7.18.
        # part.tx.origin = Point(random.random() * side, random.random() * side)

@debug_trace
def optimizer_place(parts, nets, force_func, **options):
    """Use a cost optimizer to place parts under influence of attractive nets and repulsive part overlaps.

    Args:
        parts (list): List of Parts.
        nets (list): List of nets that interconnect parts.
        force_func: Function for calculating forces between parts.
        options (dict): Dict of options and values that enable/disable functions.

    Notes:
        This is too slow even if it produced good results, which it doesn't.
    """

    if not options.get("use_optimizer"):
        # Abort if use of optimization algo for of part placement is disabled.
        return

    if len(parts) <= 1:
        # No need to do placement if there's less than two parts.
        return

    def cost(x, *args):
        # Translate the optimizer coords to part coords.
        for part, x, y in zip(parts, x[::2], x[1::2]):
            part.tx.move_to(Point(x*bbox.w, y*bbox.h))
        # Sum magnitude of force acting on each part. Lower force is better.
        for part in parts:
            part.force = force_func(part, parts, scale=scale, alpha=alpha, **options)
        return sum((part.force.magnitude for part in parts))

    # Get the placement bounding box for part coordinates.
    bbox = define_placement_bbox(parts)
    
    # Get PyGame screen, real-to-screen coord Tx matrix, font for debug drawing.
    scr = options.get("draw_scr")
    tx = options.get("draw_tx")
    font = options.get("draw_font")
    txt_org = Point(10,10)

    # Set scale factor between attractive net forces and repulsive part overlap forces.
    scale = scale_attractive_repulsive_forces(parts, force_func, **options)

    # Setup the schedule for adjusting the alpha coefficient that weights the
    # combination of the attractive net forces and the repulsive part overlap forces.
    # Start at 0 (all attractive) and gradually progress to 1 (all repulsive).
    N = 10
    alpha_schedule = [i * 1/N for i in range(N+1)]

    # Part coords for optimization are bounded between 0 and 1.
    bounds = ((0, 1),) * 2 * len(parts)

    # Step through the alpha sequence from all-attractive to all-repulsive forces.
    import scipy.optimize
    import numpy as np
    for alpha in alpha_schedule:

        if scr:
            # Draw current part placement for debugging purposes.
            draw_placement(parts, nets, scr, tx, font)
            draw_text(f"alpha:{alpha:.2f}", txt_org, scr, tx, font, color=(0, 0, 0), real=False)
            draw_redraw()

        # Translate the part coords to optimization intervals between 0 and 1.
        x0 = []
        for part in parts:
            x0.extend([part.tx.dx/bbox.w, part.tx.dy/bbox.h])
        x0 = np.array(x0)

        # Run the optimizer.
        # scipy.optimize.dual_annealing(cost, bounds)
        scipy.optimize.shgo(cost, bounds)

    if scr:
        # Draw current part placement for debugging purposes.
        draw_placement(parts, nets, scr, tx, font)
        draw_text(f"alpha:{alpha:.2f}", txt_org, scr, tx, font, color=(0, 0, 0), real=False)
        draw_redraw()


@debug_trace
def push_and_pull(parts, nets, force_func, speed, **options):
    """Move parts under influence of attractive nets and repulsive part overlaps.

    Args:
        parts (list): List of Parts.
        nets (list): List of nets that interconnect parts.
        force_func: Function for calculating forces between parts.
        speed (float): How fast parts move under the influence of forces.
        options (dict): Dict of options and values that enable/disable functions.
    """

    if not options.get("use_push_pull"):
        # Abort if push & pull of parts is disabled.
        return

    if len(parts) <= 1:
        # No need to do placement if there's less than two parts.
        return

    def cost(parts, alpha):
        for part in parts:
            part.force = force_func(part, parts, scale=scale, alpha=alpha, **options)
        return sum((part.force.magnitude for part in parts))

    # Get PyGame screen, real-to-screen coord Tx matrix, font for debug drawing.
    scr = options.get("draw_scr")
    tx = options.get("draw_tx")
    font = options.get("draw_font")
    txt_org = Point(10,10)

    # Set scale factor between attractive net forces and repulsive part overlap forces.
    scale = scale_attractive_repulsive_forces(parts, force_func, **options)

    # Make list of parts that will be moved.
    mobile_parts = parts[:]

    # Setup the schedule for adjusting the alpha coefficient that weights the
    # combination of the attractive net forces and the repulsive part overlap forces.
    # Start at 0 (all attractive) and gradually progress to 1 (all repulsive).
    N = 5
    alpha_schedule = [i * 1/N for i in range(N+1)]

    # Step through the alpha sequence going from all-attractive to all-repulsive forces.
    for alpha in alpha_schedule:

        # Clear the average movement vectors of all the parts.
        for part in mobile_parts:
            part.mv_avg = Vector(0, 0)

        # Set initial value of coef to 1 to just take initial part movement as the average.
        mv_avg_coef = 1

        # Move parts for this alpha until all the parts have settled into position. 
        while True:

            # Compute forces exerted on the parts by each other.
            for part in mobile_parts:
                part.force = force_func(part, parts, scale=scale, alpha=alpha, **options)

            # Get overall drift force across all parts. This will be subtracted so the
            # entire group of parts doesn't just continually drift off in one direction. 
            drift_force = sum([part.force for part in mobile_parts], start=Vector(0,0)) / len(mobile_parts)

            # Apply movements to part positions after subtracting the overall group drift force.
            for part in mobile_parts:

                # Apply part movement after removing overall drift movement.
                part.force -= drift_force
                part.mv = part.force * speed
                part.tx *= Tx(dx=part.mv.x, dy=part.mv.y)

                # Update the average part movement. First iteration sets average to the current move.
                part.mv_avg = (1-mv_avg_coef) * part.mv_avg + mv_avg_coef * part.mv

            # After the first iteration, set the coefficient so averages include past & present part movements.
            mv_avg_coef = 0.1

            if scr:
                # Draw current part placement for debugging purposes.
                draw_placement(parts, nets, scr, tx, font)
                mv_avg = sum(part.mv_avg.magnitude for part in mobile_parts)
                draw_text(f"alpha:{alpha:3.2f}  cost:{cost(mobile_parts, alpha):6.1f}  move:{mv_avg}", txt_org, scr, tx, font, color=(0, 0, 0), real=False)
                draw_redraw()

            if alpha == alpha_schedule[-1]:
                stillness_coef = 0.001
            else:
                stillness_coef = 0.01
            if all(p.mv_avg.magnitude < stillness_coef*(p.place_bbox.w + p.place_bbox.h) for p in mobile_parts):
                break


@debug_trace
def jump_parts(parts, force_func, speed, **options):
    """Jump parts to move them over other parts that block them.

    Args:
        parts (list): List of Parts.
        force_func: Function for calculating forces between parts.
        speed (float): How fast parts move under the influence of forces.
        options (dict): Dict of options and values that enable/disable functions.
    """

    if not options.get("allow_jumps"):
        # Abort if jumping parts is disabled.
        return

    # Get PyGame screen, real-to-screen coord Tx matrix, font for debug drawing.
    scr = options.get("draw_scr")
    tx = options.get("draw_tx")
    font = options.get("draw_font")

    for _ in range(1): # TODO: ad-hoc iteration count.

        # Sort the parts to find the one with the most attractive force trying to move it
        # but it can't move because it is blocked by other parts.
        jump_parts = sorted(parts, key=lambda p:force_func(p, parts, alpha=0, **options).magnitude, reverse=True)
        jump_parts = jump_parts[:3]
        print([p.ref for p in jump_parts])
        draw_pause()

        while jump_parts:
            # Pop the best part to move and move it based on attractive forces only.
            part = jump_parts.pop()
            # N = 200
            alpha = 0
            # for alpha in (i*1.0/N for i in range(N+1)):
            for _ in range(round(1/speed)):
                mv = force_func(part, parts, alpha=alpha, **options)
                mv *= speed
                mv_tx = Tx(dx=mv.x, dy=mv.y)
                part.tx *= mv_tx

            # Re-sort remaining parts to find the best one to move.
            jump_parts = sorted(jump_parts, key=lambda p:force_func(p, parts, alpha=0, **options).magnitude, reverse=True)

        if scr:
            # Draw current part placement for debugging purposes.
            draw_placement(parts, [], scr, tx, font)
            draw_pause()

@debug_trace
def align_parts(parts, **options):
    """Move parts to align their I/O pins with each other and reduce routing jagginess.

    Args:
        parts (list): List of Parts.
        options (dict): Dict of options and values that enable/disable functions.
    """

    if not options.get("align_parts"):
        # Abort if aligning parts is disabled.
        return

    try:
        # Align higher pin-count parts first so smaller parts can align to them later without changes messing it up.
        mobile_parts = sorted(parts[:], key=lambda prt: -len(prt.pins))
    except AttributeError:
        # Not a set of Parts. Must be PartBlocks. Skip alignment.
        return

    # Get PyGame screen, real-to-screen coord Tx matrix, font for debug drawing.
    scr = options.get("draw_scr")
    tx = options.get("draw_tx")
    font = options.get("draw_font")

    for part in mobile_parts:

        # Collect moves to align each pin connected to pins on other parts.
        align_moves = []
        for net, anchor_pins in part.anchor_pins.items():
            pull_pins = part.pull_pins[net]
            for pull_pin in pull_pins:
                pull_pt = pull_pin.place_pt * pull_pin.part.tx
                for anchor_pin in anchor_pins:
                    anchor_pt = anchor_pin.place_pt * anchor_pin.part.tx
                    align_moves.append(pull_pt - anchor_pt)

        if not align_moves:
            # The part wasn't connected to any other parts, so skip alignment.
            continue

        # Select the smallest alignment move that occurs most frequently,
        # meaning it will align the most pins with the least movement.
        best_moves = Counter(align_moves).most_common(1)
        best_moves.sort(key=lambda mv: min(abs(mv[0].x), abs(mv[0].y)))
        best_move = best_moves[0][0]

        # Align either in X or Y direction, whichever requires the smallest movement.
        if abs(best_move.x) > abs(best_move.y):
            # Align by moving in Y direction.
            best_move.x = 0
        else:
            # Align by moving in X direction.
            best_move.y = 0

        # Align the part.
        tx = Tx(dx=best_move.x, dy=best_move.y)
        part.tx *= tx

        if scr:
            # Draw current part placement for debugging purposes.
            draw_placement(parts, [], scr, tx, font)


@debug_trace
def remove_overlaps(parts, nets, **options):
    """Remove any overlaps using horz/vert grid movements.

    Args:
        parts (list): List of Parts.
        nets (list): List of nets that interconnect parts.
        options (dict): Dict of options and values that enable/disable functions.
    """

    if len(parts) <= 1:
        # No need to do placement if there's less than two parts.
        return

    # Get PyGame screen, real-to-screen coord Tx matrix, font for debug drawing.
    scr = options.get("draw_scr")
    tx = options.get("draw_tx")
    font = options.get("draw_font")

    # Make list of parts that will be moved.
    # mobile_parts = parts[:-1]  # Keep one part stationary as an anchor.
    mobile_parts = parts[:]  # Move all parts.

    overlaps = True
    while overlaps:

        overlaps = False
        for part in mobile_parts:
            shove_force = repulsive_force(part, parts, **options)
            part.mv = Vector(sgn(shove_force.x), sgn(shove_force.y)) * GRID

        # Get overall drift movement across all parts.
        drift_mv = sum([part.mv for part in mobile_parts], start=Vector(0,0)) / len(mobile_parts)

        # Apply movements to part positions after subtracting the overall group drift.
        for part in mobile_parts:
            mv = part.mv - drift_mv
            mv_tx = Tx(dx=mv.x, dy=mv.y)
            part.tx *= mv_tx  # Move part.

        if scr:
            draw_placement(parts, nets, scr, tx, font)


@debug_trace
def slip_and_slide(parts, nets, force_func, **options):
    """Move parts on horz/vert grid looking for improvements without causing overlaps.

    Args:
        parts (list): List of Parts.
        nets (list): List of nets that interconnect parts.
        force_func: Function for calculating forces between parts.
        options (dict): Dict of options and values that enable/disable functions.
    """

    if not options.get("slip_and_slide"):
        # Abort if this is disabled.
        return

    if len(parts) <= 1:
        # No need to do placement if there's less than two parts.
        return

    if not nets:
        # No need to do this if there are no nets attracting parts together.
        return

    # Set scale factor between attractive net forces and repulsive part overlap forces.
    scale = scale_attractive_repulsive_forces(parts, force_func, **options)

    # Get PyGame screen, real-to-screen coord Tx matrix, font for debug drawing.
    scr = options.get("draw_scr")
    tx = options.get("draw_tx")
    font = options.get("draw_font")

    # Make list of parts that will be moved.
    # mobile_parts = parts[:-1]  # Keep one part stationary as an anchor.
    mobile_parts = parts[:]  # Move all parts.

    moved = True
    iterations = 20  # TODO: Ad-hoc from observation on test_generate.py.
    while moved and iterations:
        moved = False
        random.shuffle(mobile_parts)
        for part in mobile_parts:
            smallest_force = force_func(part, parts, alpha=0, scale=scale, **options).magnitude
            best_tx = copy(part.tx)
            for dx, dy in ((-GRID, 0), (GRID, 0), (0, -GRID), (0, -GRID)):
                mv_tx = Tx(dx=dx, dy=dy)
                part.tx = part.tx * mv_tx
                force = force_func(part, parts, alpha=0, scale=scale, **options).magnitude
                if force < smallest_force:
                    if repulsive_force(part, parts).magnitude == 0:
                        smallest_force = force
                        best_tx = copy(part.tx)
                        moved = True
            part.tx = best_tx
        iterations -= 1
        if scr:
            draw_placement(parts, nets, scr, tx, font)


@debug_trace
def evolve_placement(parts, nets, force_func, speed, **options):
    """Evolve part placement looking for optimum using force function.

    Args:
        parts (list): List of Parts.
        nets (list): List of nets that interconnect parts.
        force_func (function): Computes the force affecting part positions.
        speed (float): Speed of part movement per unit of force.
        options (dict): Dict of options and values that enable/disable functions.
    """

    # Force-directed placement.
    push_and_pull(parts, nets, force_func, speed, **options)

    # Use a scipy.optimize algorithm for placement.
    # optimizer_place(parts, nets, force_func, **options)

    # Jump parts around to reduce wire length.
    jump_parts(parts, force_func, speed, **options)

    # Line-up the parts to reduce routing jagginess.
    align_parts(parts, **options)

    # Snap parts to grid.
    for part in parts:
        snap_to_grid(part)

    # Remove part overlaps.
    remove_overlaps(parts, nets, **options)

    # Look for local improvements.
    slip_and_slide(parts, nets, force_func, **options)


@export_to_all
class Placer:
    """Mixin to add place function to Node class."""

    # Speed of part movement during placement.
    speed = 0.25
    # speed = 0.10
    # speed = 0.05
    # speed = 0.01 # Poor: push_and_pull() thinks parts have stabilized when they haven't.

    def group_parts(node, **options):
        """Group parts in the Node that are connected by internal nets

        Args:
            node (Node): Node with parts.
            options (dict, optional): Dictionary of options and values. Defaults to {}.

        Returns:
            list: List of lists of Parts that are connected.
            list: List of internal nets connecting parts.
            list: List of Parts that are not connected to anything (floating).
        """

        if not node.parts:
            return [], [], []

        # Extract list of nets having at least one pin in the node.
        internal_nets = node.get_internal_nets()

        # Remove some nets according to options.
        if options.get("remove_power"):

            def is_pwr(net):
                return (
                    net.netclass == "Power"
                    or "vcc" in net.name.lower()
                    or "gnd" in net.name.lower()
                )

            internal_nets = [net for net in internal_nets if not is_pwr(net)]

        if options.get("remove_high_fanout"):
            import statistics

            fanouts = [len(net) for net in internal_nets]
            try:
                fanout_mean = statistics.mean(fanouts)
                fanout_stdev = statistics.stdev(fanouts)
            except statistics.StatisticsError:
                pass
            else:
                fanout_threshold = fanout_mean + 2 * fanout_stdev
                internal_nets = [
                    net for net in internal_nets if len(net) < fanout_threshold
                ]

        # Group all the parts that have some interconnection to each other.
        # Start with groups of parts on each individual net.
        connected_parts = [
            set(pin.part for pin in net.pins if pin.part in node.parts)
            for net in internal_nets
        ]

        # Now join groups that have parts in common.
        for i in range(len(connected_parts) - 1):
            group1 = connected_parts[i]
            for j in range(i + 1, len(connected_parts)):
                group2 = connected_parts[j]
                if group1 & group2:
                    # If part groups intersect, collect union of parts into one group
                    # and empty-out the other.
                    connected_parts[j] = connected_parts[i] | connected_parts[j]
                    connected_parts[i] = set()
                    # No need to check against group1 any more since it has been
                    # unioned into group2 that will be checked later in the loop.
                    break

        # Remove any empty groups that were unioned into other groups.
        connected_parts = [group for group in connected_parts if group]

        # Find parts that aren't connected to anything.
        floating_parts = set(node.parts) - set(itertools.chain(*connected_parts))

        return connected_parts, internal_nets, floating_parts

    def place_connected_parts(node, parts, nets, **options):
        """Place individual parts.

        Args:
            node (Node): Node with parts.
            parts (list): List of Part sets connected by nets.
            nets (list): List of internal Nets connecting the parts.
            options (dict): Dict of options and values that enable/disable functions.
        """

        if not parts:
            # Abort if nothing to place.
            return

        # Add bboxes with surrounding area so parts are not butted against each other.
        add_placement_bboxes(parts, **options)

        # Set anchor and pull pins that determine attractive forces between parts.
        add_anchor_pull_pins(parts, nets, **options)

        # Randomly place connected parts.
        random_placement(parts)

        if options.get("draw_placement"):
            # Draw the placement for debug purposes.
            bbox = BBox()
            for part in parts:
                tx_bbox = part.place_bbox * part.tx
                bbox.add(tx_bbox)
            draw_scr, draw_tx, draw_font = draw_start(bbox)
            options.update(
                {"draw_scr": draw_scr, "draw_tx": draw_tx, "draw_font": draw_font}
            )

        if options.get("compress_before_place"):
            central_placement(parts, **options)

        # Do force-directed placement of the parts in the parts.
        evolve_placement(
            parts, nets, total_part_force, speed=Placer.speed, **options
        )

        if options.get("rotate_parts"):
            # Adjust part orientations.
            if adjust_orientations(parts, **options):

                # Some part orientations were changed, so re-do placement.
                evolve_placement(
                    parts, nets, total_part_force, speed=Placer.speed, **options
                )

        if options.get("draw_placement"):
            # Pause to look at placement for debugging purposes.
            draw_pause()

    def place_floating_parts(node, parts, **options):
        """Place individual parts.

        Args:
            node (Node): Node with parts.
            parts (list): List of Parts not connected by explicit nets.
            options (dict): Dict of options and values that enable/disable functions.
        """

        if not parts:
            # Abort if nothing to place.
            return

        # Add bboxes with surrounding area so parts are not butted against each other.
        add_placement_bboxes(parts)

        # Set anchor and pull pins that determine attractive forces between similar parts.
        add_anchor_pull_pins(parts, [], **options)

        # Randomly place the floating parts.
        random_placement(parts)

        if options.get("draw_placement"):
            # Compute the drawing area for the floating parts
            bbox = BBox()
            for part in parts:
                tx_bbox = part.place_bbox * part.tx
                bbox.add(tx_bbox)
            draw_scr, draw_tx, draw_font = draw_start(bbox)
            options.update(
                {"draw_scr": draw_scr, "draw_tx": draw_tx, "draw_font": draw_font}
            )

        # For non-connected parts, do placement based on their similarity to each other.
        part_similarity = defaultdict(lambda: defaultdict(lambda: 0))
        for part in parts:
            for other_part in parts:

                # Don't compute similarity of a part to itself.
                if other_part is part:
                    continue

                # TODO: Get similarity forces right-sized.
                part_similarity[part][other_part] = part.similarity(other_part) / 100
                # part_similarity[part][other_part] = 0.1

            # Select the top-most pin in each part as the anchor point for force-directed placement.
            # tx = part.tx
            # part.anchor_pin = max(part.anchor_pins, key=lambda pin: (pin.place_pt * tx).y)

        force_func = functools.partial(
            total_similarity_force, similarity=part_similarity
        )

        if options.get("compress_before_place"):
            # Compress all floating parts together.
            central_placement(parts, **options)

        # Do force-directed placement of the parts in the group.
        evolve_placement(parts, [], force_func, speed=Placer.speed, **options)

        if options.get("draw_placement"):
            # Pause to look at placement for debugging purposes.
            draw_pause()

    def place_blocks(node, connected_parts, floating_parts, children, **options):
        """Place blocks of parts and hierarchical sheets.

        Args:
            node (Node): Node with parts.
            connected_parts (list): List of Part sets connected by nets.
            floating_parts (set): Set of Parts not connected by any of the internal nets.
            children (list): Child nodes in the hierarchy.
            non_sheets (list): Hierarchical set of Parts that are visible.
            sheets (list): List of hierarchical blocks.
            options (dict): Dict of options and values that enable/disable functions.
        """

        # Global dict of pull pins for all blocks as they each pull on each other the same way.
        block_pull_pins = defaultdict(list)

        # Class for movable groups of parts/child nodes.
        class PartBlock:
            def __init__(self, src, bbox, anchor_pt, snap_pt, tag):

                self.src = src  # Source for this block.
                self.place_bbox = bbox  # FIXME: Is this needed if place_bbox includes room for routing?

                # Create anchor pin to which forces are applied to this block.
                anchor_pin = Pin()
                anchor_pin.part = self
                anchor_pin.place_pt = anchor_pt

                # This block has only a single anchor pin, but it needs to be in a list
                # in a dict so it can be processed by the part placement functions.
                self.anchor_pins = dict()
                self.anchor_pins["similarity"] = [anchor_pin]

                # Anchor pin for this block is also a pulling pin for all other blocks.
                block_pull_pins["similarity"].append(anchor_pin)

                # All blocks have the same set of pulling pins because they all pull each other.
                self.pull_pins = block_pull_pins

                self.snap_pt = snap_pt  # For snapping to grid.
                self.tx = Tx()  # For placement.
                self.ref = "REF"  # Name for block in debug drawing.
                self.tag = tag  # TODO: what is this for?

        # Create a list of blocks from the groups of interconnected parts and the group of floating parts.
        part_blocks = []
        for part_list in connected_parts + [floating_parts]:

            if not part_list:
                # No parts in this list for some reason...
                continue

            # Find snapping point and bounding box for this group of parts.
            snap_pt = None
            bbox = BBox()
            for part in part_list:
                bbox.add(part.lbl_bbox * part.tx)
                if not snap_pt:
                    # Use the first snapping point of a part you can find.
                    snap_pt = get_snap_pt(part)

            # Tag indicates the type of part block.
            tag = 2 if (part_list is floating_parts) else 1

            # pad the bounding box so part blocks don't butt-up against each other.
            pad = BLK_EXT_PAD
            bbox = bbox.resize(Vector(pad, pad))

            # Create the part block and place it on the list.
            part_blocks.append(PartBlock(part_list, bbox, bbox.ctr, snap_pt, tag))

        # Add part blocks for child nodes.
        for child in children:

            # Calculate bounding box of child node.
            bbox = child.calc_bbox()

            # Set padding for separating bounding box from others.
            if child.flattened:
                # This is a flattened node so the parts will be shown.
                # Set the padding to include a pad between the parts and the
                # graphical box that contains them, plus the padding around
                # the outside of the graphical box.
                pad = BLK_INT_PAD + BLK_EXT_PAD
            else:
                # This is an unflattened child node showing no parts on the inside
                # so just pad around the outside of its graphical box.
                pad = BLK_EXT_PAD
            bbox.resize(Vector(pad, pad))

            # Set the grid snapping point and tag for this child node.
            snap_pt = child.get_snap_pt()
            tag = 3  # Standard child node.
            if not snap_pt:
                # No snap point found, so just use the center of the bounding box.
                snap_pt = bbox.ctr
                tag = 4  # A child node with no snapping point.

            # Create the child block and place it on the list.
            part_blocks.append(PartBlock(child, bbox, bbox.ctr, snap_pt, tag))

        # Get ordered list of all block tags. Use this list to tell if tags are
        # adjacent since there may be missing tags if a particular type of block
        # isn't present.
        tags = sorted({blk.tag for blk in part_blocks})

        # Tie the blocks together with strong links between blocks with the same tag,
        # and weaker links between blocks with adjacent tags. This ties similar
        # blocks together into "super blocks" and ties the super blocks into a linear
        # arrangement (1 -> 2 -> 3 ->...).
        blk_attr = defaultdict(lambda: defaultdict(lambda: 0))
        for blk in part_blocks:
            for other_blk in part_blocks:
                if blk is other_blk:
                    # No attraction between a block and itself.
                    continue
                if blk.tag == other_blk.tag:
                    # Large attraction between blocks of same type.
                    blk_attr[blk][other_blk] = 1
                elif abs(tags.index(blk.tag) - tags.index(other_blk.tag)) == 1:
                    # Some attraction between blocks of adjacent types.
                    blk_attr[blk][other_blk] = 0.1
                else:
                    # Otherwise, no attraction between these blocks.
                    blk_attr[blk][other_blk] = 0

        if not part_blocks:
            # Abort if nothing to place.
            return

        # Start off with a random placement of part blocks.
        random_placement(part_blocks)

        if options.get("draw_placement"):
            # Setup to draw the part block placement for debug purposes.
            bbox = BBox()
            for blk in part_blocks:
                tx_bbox = blk.place_bbox * blk.tx
                bbox.add(tx_bbox)
            draw_scr, draw_tx, draw_font = draw_start(bbox)
            options.update(
                {"draw_scr": draw_scr, "draw_tx": draw_tx, "draw_font": draw_font}
            )

        # Arrange the part blocks with similarity force-directed placement.
        force_func = functools.partial(total_similarity_force, similarity=blk_attr)
        evolve_placement(part_blocks, [], force_func, speed=Placer.speed, **options)

        if options.get("draw_placement"):
            # Pause to look at placement for debugging purposes.
            draw_pause()

        # Apply the placement moves of the part blocks to their underlying sources.
        for blk in part_blocks:
            try:
                # Update the Tx matrix of the source (usually a child node).
                blk.src.tx = blk.tx
            except AttributeError:
                # The source doesn't have a Tx so it must be a collection of parts.
                # Apply the block placement to the Tx of each part.
                for part in blk.src:
                    part.tx *= blk.tx

    def get_attrs(node):
        """Return dict of attribute sets for the parts, pins, and nets in a node."""
        attrs = {"parts":set(), "pins": set(), "nets":set()}
        for part in node.parts:
            attrs["parts"].update(set(dir(part)))
            for pin in part.pins:
                attrs["pins"].update(set(dir(pin)))
        for net in node.get_internal_nets():
            attrs["nets"].update(set(dir(net)))
        return attrs

    def show_added_attrs(node):
        """Show attributes that were added to parts, pins, and nets in a node."""
        current_attrs = node.get_attrs()
        for key in current_attrs.keys():
            print("added {} attrs: {}".format(key, current_attrs[key] - node.attrs[key]))

    def rmv_placement_stuff(node):
        """Remove attributes added to parts, pins, and nets of a node during the placement phase."""

        for part in node.parts:
            rmv_attr(part.pins, ("route_pt", "place_pt"))
        rmv_attr(node.parts, ("anchor_pins", "pull_pins", "pin_ctrs", "force", "mv", "mv_avg"))
        rmv_attr(node.get_internal_nets(), ("parts",))


    def place(node, tool=None, **options):
        """Place the parts and children in this node.

        Args:
            node (Node): Hierarchical node containing the parts and children to be placed.
            tool (str): Backend tool for schematics.
            options (dict): Dictionary of options and values to control placement.
        """

        # Inject the constants for the backend tool into this module.
        import skidl
        from skidl.tools import tool_modules

        tool = tool or skidl.get_default_tool()
        this_module = sys.modules[__name__]
        this_module.__dict__.update(tool_modules[tool].constants.__dict__)

        random.seed(options.get("seed"))

        # Store the starting attributes of the node's parts, pins, and nets.
        node.attrs = node.get_attrs()

        try:

            # First, recursively place children of this node.
            # TODO: Child nodes are independent, so can they be processed in parallel?
            for child in node.children.values():
                child.place(tool=tool, **options)

            # Group parts into those that are connected by explicit nets and
            # those that float freely connected only by stub nets.
            connected_parts, internal_nets, floating_parts = node.group_parts(**options)

            # Place each group of connected parts.
            for group in connected_parts:
                node.place_connected_parts(list(group), internal_nets, **options)

            # Place the floating parts that have no connections to anything else.
            node.place_floating_parts(list(floating_parts), **options)

            # Now arrange all the blocks of placed parts and the child nodes within this node.
            node.place_blocks(
                connected_parts, floating_parts, node.children.values(), **options
            )

            # Remove any stuff leftover from this place & route run.
            # print(f"added part attrs = {new_part_attrs}")
            node.rmv_placement_stuff()
            node.show_added_attrs()

            # Calculate the bounding box for the node after placement of parts and children.
            node.calc_bbox()

        except PlacementFailure:
            node.rmv_placement_stuff()
            raise PlacementFailure


    def get_snap_pt(node):
        """Get a Point to use for snapping the node to the grid.

        Args:
            node (Node): The Node to which the snapping point applies.

        Returns:
            Point: The snapping point or None.
        """

        if node.flattened:

            # Look for a snapping point based on one of its parts.
            for part in node.parts:
                snap_pt = get_snap_pt(part)
                if snap_pt:
                    return snap_pt

            # If no part snapping point, look for one in its children.
            for child in node.children.values():
                if child.flattened:
                    snap_pt = child.get_snap_pt()
                    if snap_pt:
                        # Apply the child transformation to its snapping point.
                        return snap_pt * child.tx

        # No snapping point if node is not flattened or no parts in it or its children.
        return None
