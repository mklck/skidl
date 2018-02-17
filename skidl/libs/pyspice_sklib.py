# -*- coding: utf-8 -*-

# MIT license
#
# Copyright (C) 2018 by XESS Corp.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

"""
An interface from SKiDL to PySpice.
"""

# Create a SKiDL library of SPICE elements. All PySpice-related info goes into
# a pyspice dictionary that is added as an attribute to the SKiDL Part object.


from skidl import Pin, Part, SchLib, SKIDL, TEMPLATE
from skidl.tools.spice import not_implemented, add_part_to_circuit

pyspice_lib = SchLib(tool=SKIDL).add_parts(*[
    Part(
        name='A',
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='XSPICE',
        description='XSPICE code module',
        ref_prefix='A',
        pyspice={
            'name': 'A',
            'pos': ('model', ),
            'kw': [],
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[]),
    Part(
        name='B',
        aliases=['behavsrc', 'BEHAVSRC', 'behavioralsource', 'BEHAVIORALSOURCE',],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='Behavioral source',
        description='Behavioral (arbitrary) source',
        ref_prefix='B',
        pyspice={
            'name': 'B',
            'pos': [],
            'kw': ('i', 'i_expression', 'v', 'v_expression', 'tc1', 'tc2',
                'temp', 'temperature', 'dtemp', 'device_temperature',),
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='p', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='n', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='C',
        aliases=['cap', 'CAP'],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='cap capacitor',
        description='Capacitor',
        ref_prefix='C',
        pyspice={
            'name': 'C',
            'pos': ('value', ),
            'kw': ('model', 'multiplier', 'm', 'scale', 'temperature', 'temp',
                   'device_temperature', 'dtemp', 'initial_condition', 'ic'),
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='p', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='n', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='BEHAVCAP',
        aliases=['behavcap', 'behavioralcap', 'BEHAVIORALCAP',],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='behavioral capacitor',
        description='Behavioral capacitor',
        ref_prefix='C',
        pyspice={
            'name': 'BehavioralCapacitor',
            'pos': ('expression', ),
            'kw': ('tc1', 'tc2'),
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='p', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='n', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='SEMICAP',
        aliases=['semicap', 'semiconductorcap', 'SEMICONDUCTORCAP',],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='semiconductor capacitor',
        description='Semiconductor capacitor',
        ref_prefix='C',
        pyspice={
            'name': 'SemiconductorCapacitor',
            'pos': ('value', 'model', ),
            'kw': ('length', 'l', 'width', 'w', 'multiplier', 'm', 'scale', 'temperature', 'temp',
                   'device_temperature', 'dtemp', 'initial_condition', 'ic'),
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='p', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='n', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='D',
        aliases=['diode', 'DIODE'],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='diode rectifier',
        description='Diode',
        ref_prefix='D',
        pyspice={
            'name': 'D',
            'pos': [],
            'kw': ('model', 'area', 'multiplier', 'm', 'pj', 'off', 'ic', 'temperature',
                   'temp', 'device_temperature', 'dtemp'),
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='p', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='n', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='E',
        aliases=['VCVS', 'vcvs'],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='voltage-controlled voltage source',
        description='Voltage-controlled voltage source',
        ref_prefix='E',
        pyspice={
            'name': 'VCVS',
            'pos': ('gain',),
            'kw': [],
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='ip', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='in', func=Pin.PASSIVE, do_erc=True),
            Pin(num='3', name='op', func=Pin.PASSIVE, do_erc=True),
            Pin(num='4', name='on', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='NONLINV',
        aliases=['nonlinv', 'nonlinearvoltagesource', 'NONLINEARVOLTAGESOURCE'],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='non-linear voltage source',
        description='Nonlinear voltage source',
        ref_prefix='E',
        pyspice={
            'name': 'NonLinearVoltageSource',
            'pos': [],
            'kw': ('expression', 'table',),
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='p', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='n', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='F',
        aliases=['CCCS', 'cccs'],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='current-controlled current source',
        description='Current-controlled current source',
        ref_prefix='F',
        pyspice={
            'name': 'CCCS',
            'pos': ('control', 'gain', ),
            'kw': ('multiplier', 'm', ),
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='p', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='n', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='G',
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='voltage-controlled current source',
        description='Voltage-controlled current source',
        ref_prefix='G',
        pyspice={
            'name': 'VCCS',
            'pos': ('transconductance', ),
            'kw': ('multiplier', 'm',),
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='ip', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='in', func=Pin.PASSIVE, do_erc=True),
            Pin(num='3', name='op', func=Pin.PASSIVE, do_erc=True),
            Pin(num='4', name='on', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='NONLINI',
        aliases=['nonlinvi', 'nonlinearcurrentsource', 'NONLINEARCURRENTSOURCE'],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='non-linear current source',
        description='Nonlinear current source',
        ref_prefix='G',
        pyspice={
            'name': 'NonLinearCurrentSource',
            'pos': [],
            'kw': ('expression', 'table',),
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='p', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='n', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='H',
        aliases=['CCVS', 'ccvs'],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='current-controlled voltage source',
        description='Current-controlled voltage source',
        ref_prefix='H',
        pyspice={
            'name': 'H',
            'pos': ('control', 'transresistance', ),
            'kw': [],
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='p', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='n', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='I',
        aliases=['cs', 'CS'],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='current source',
        description='Current source',
        ref_prefix='I',
        pyspice={
            'name': 'I',
            'pos': ('dc_value', ),
            'kw': [],
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='p', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='n', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='J',
        aliases=['JFET', 'jfet'],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='junction field-effect transistor JFET',
        description='Junction field-effect transistor',
        ref_prefix='J',
        pyspice={
            'name': 'J',
            'pos': ('model',),
            'kw': ('area', 'multiplier', 'm', 'off', 'ic', 'temperature', 'temp'),
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='D', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='G', func=Pin.PASSIVE, do_erc=True),
            Pin(num='3', name='S', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='K',
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='coupled mutual inductors',
        description='Coupled (mutual) inductors',
        ref_prefix='K',
        pyspice={
            'name': 'K',
            'pos': ('ind1', 'ind2', 'coupling',),
            'kw': [],
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        coupled_parts=[],
        pins=[]),
    Part(
        name='L',
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='inductor choke coil reactor magnetic',
        description='Inductor',
        ref_prefix='L',
        pyspice={
            'name': 'L',
            'pos': ('value', 'model'),
            'kw': ('nt', 'multiplier', 'm', 'scale', 'temperature', 'temp',
                   'device_temperature', 'dtemp', 'initial_condition','ic'),
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='p', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='n', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='BEHAVIND',
        aliases=['behavind', 'behavioralind', 'BEHAVIORALIND',],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='behavioral inductor',
        description='Behavioral inductor',
        ref_prefix='C',
        pyspice={
            'name': 'BehavioralInductor',
            'pos': ('expression', ),
            'kw': ('tc1', 'tc2'),
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='p', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='n', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='M',
        aliases=['MOSFET', 'mosfet', 'FET', 'fet',],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='metal-oxide field-effect transistor MOSFET',
        description='Metal-oxide field-effect transistor',
        ref_prefix='M',
        pyspice={
            'name': 'M',
            #'pos': ('model',),
            'pos': [],
            'kw': ('model', 'multiplier', 'm', 'length', 'l', 'width', 'w',
                   'drain_area', 'ad', 'source_area', 'as', 'drain_perimeter', 'pd',
                   'source_perimeter', 'ps', 'drain_number_square', 'nrd',
                   'source_number_square', 'nrs', 'off', 'ic', 'temperature', 'temp'),
            'optional_pins': {'D':'drain', 'G':'gate', 'S':'source', 'B':'bulk'},
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='D', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='G', func=Pin.PASSIVE, do_erc=True),
            Pin(num='3', name='S', func=Pin.PASSIVE, do_erc=True),
            Pin(num='4', name='B', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part( #####################################################################
        name='N',
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='numerical device GSS',
        description='Numerical device for GSS',
        ref_prefix='N',
        pyspice={
            'name': 'N',
            'add': not_implemented,
        },
        num_units=1,
        do_erc=True,
        pins=[]),
    Part(
        name='O',
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='lossy transmission line',
        description='Lossy transmission line',
        ref_prefix='O',
        pyspice={
            'name': 'O',
            'pop': ('model',),
            'kw': [],
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='ip', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='in', func=Pin.PASSIVE, do_erc=True),
            Pin(num='3', name='op', func=Pin.PASSIVE, do_erc=True),
            Pin(num='4', name='on', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='P',
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='coupled multiconductor line',
        description='Coupled multiconductor line',
        ref_prefix='P',
        pyspice={
            'name': 'P',
            'pop': ('model',),
            'kw': ('length', 'l',),
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        #model=
        pins=[]),
    Part(
        name='Q',
        aliases=('BJT', 'bjt'),
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='bipolar transistor npn pnp',
        description='Bipolar Junction Transistor',
        ref_prefix='Q',
        pyspice={
            'name': 'Q',
            'pos': [],
            'kw': ('model', 'area', 'areac', 'areab',
                   'multiplier', 'm', 'off', 'ic', 'temperature', 'temp',
                   'device_temperature', 'dtemp'),
            'optional_pins': {'C':'collector', 'B':'base', 'E':'emitter', 'S':'substrate'},
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='C', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='B', func=Pin.PASSIVE, do_erc=True),
            Pin(num='3', name='E', func=Pin.PASSIVE, do_erc=True),
            Pin(num='4', name='S', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='R',
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='res resistor',
        description='Resistor',
        ref_prefix='R',
        pyspice={
            'name': 'R',
            'pos': ('value', ),
            'kw': ('ac', 'multiplier', 'm', 'scale', 'temperature', 'temp',
                   'device_temperature', 'dtemp', 'noisy'),
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='p', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='n', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='BEHAVRES',
        aliases=['behavres', 'behavioralresistor', 'BEHAVIORALRESISTOR',],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='behavioral resistor',
        description='Behavioral resistor',
        ref_prefix='R',
        pyspice={
            'name': 'BehavioralResistor',
            'pos': ('expression',),
            'kw': ('tc1', 'tc2'),
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='p', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='n', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='SEMIRES',
        aliases=['semires', 'semiconductorresistor', 'SEMICONDUCTORRESISTOR',],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='semiconductor resistor',
        description='Semiconductor resistor',
        ref_prefix='R',
        pyspice={
            'name': 'SemiconductorResistor',
            'pos': ('value', 'model',),
            'kw': ('ac', 'length', 'l', 'width', 'w', 'multiplier', 'm',
                    'scale', 'temperature', 'temp',
                    'device_temperature', 'dtemp', 'noisy'),
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='p', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='n', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='S',
        aliases=['VCS', 'vcs'],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='voltage-controlled switch',
        description='Voltage-controlled switch',
        ref_prefix='S',
        pyspice={
            'name': 'S',
            'pos': [],
            'kw': ('model', 'initial_state',),
            'optional_pins': {'op':'output_plus', 'on':'output_minus', 'ip':'input_plus', 'in':'input_minus'},
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='op', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='on', func=Pin.PASSIVE, do_erc=True),
            Pin(num='3', name='ip', func=Pin.PASSIVE, do_erc=True),
            Pin(num='4', name='in', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='T',
        aliases=['transmissionline', 'TRANSMISSIONLINE'],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='transmission line',
        description='Transmission line',
        ref_prefix='T',
        pyspice={
            'name': 'TransmissionLine',
            'add': add_part_to_circuit,
            'pos': [],
            'kw': ('impedance', 'Z0', 'time_delay', 'TD', 'frequency', 'F',
                'normalized_length', 'NL',),
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='ip', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='in', func=Pin.PASSIVE, do_erc=True),
            Pin(num='3', name='op', func=Pin.PASSIVE, do_erc=True),
            Pin(num='4', name='on', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='U',
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='uniformly-distributed RC line',
        description='Uniformly-distributed RC line',
        ref_prefix='U',
        pyspice={
            'name': 'U',
            'pos': ('model',),
            'kw': ('length', 'l', 'number_of_lumps', 'm',),
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[]),
    Part(
        name='V',
        aliases=['v', 'AMMETER', 'ammeter',],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='voltage source',
        description='Voltage source',
        ref_prefix='V',
        pyspice={
            'name': 'V',
            'pos': ('dc_value',),
            'kw': [],
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='p', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='n', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='W',
        aliases=['CCS', 'ccs'],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='current-controlled switch',
        description='Current-controlled switch',
        ref_prefix='W',
        pyspice={
            'name': 'W',
            'pos': [],
            'kw': ('source', 'model', 'initial_state',),
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='p', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='n', func=Pin.PASSIVE, do_erc=True),
        ]),
    # Part( #####################################################################
        # name='X',
        # dest=TEMPLATE,
        # tool=SKIDL,
        # keywords='subcircuit',
        # description='Subcircuit',
        # ref_prefix='Y',
        # pyspice={
            # 'name': 'SubCircuitElement',
            # 'add': _add_subcircuit_to_circuit,
        # },
        # num_units=1,
        # do_erc=True,
        # pins=[]),
    Part(
        name='Y',
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='single lossy transmission line',
        description='Single lossy transmission line',
        ref_prefix='Y',
        pyspice={
            'name': 'Y',
            'pos': ('model',),
            'kw': ('length', 'len',),
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        #model=
        pins=[]),
    Part(
        name='Z',
        aliases=['MESFET', 'mesfet'],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='metal-semiconductor field-effect transistor MOSFET',
        description='Metal-semiconductor field-effect transistor',
        ref_prefix='Z',
        pyspice={
            'name': 'Z',
            'pos': ('model',),
            'kw': ('area', 'multiplier', 'm', 'off', 'ic',),
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='D', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='G', func=Pin.PASSIVE, do_erc=True),
            Pin(num='3', name='S', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='SINEV',
        aliases=['sinev', 'sinusoidalvoltage', 'SINUSOIDALVOLTAGE'],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='simusoidal voltage source',
        description='Sinusoidal voltage source',
        ref_prefix='V',
        pyspice={
            'name': 'SinusoidalVoltageSource',
            'pos': [],
            'kw': ['dc_offset', 'offset', 'amplitude', 'frequency', 'delay', 'damping_factor'],
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='p', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='n', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='SINEI',
        aliases=['sinei', 'sinusoidalcurrent', 'SINUSOIDALCURRENT'],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='simusoidal current source',
        description='Sinusoidal current source',
        ref_prefix='I',
        pyspice={
            'name': 'SinusoidalCurrentSource',
            'pos': [],
            'kw': ['dc_offset', 'offset', 'amplitude', 'frequency', 'delay', 'damping_factor'],
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='p', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='n', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='PULSEV',
        aliases=['pulsev', 'pulsevoltage', 'PULSEVOLTAGE'],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='pulsed voltage source',
        description='Pulsed voltage source',
        ref_prefix='V',
        pyspice={
            'name': 'PulseVoltageSource',
            'pos': [],
            'kw': ['initial_value', 'pulsed_value', 'delay_time', 'rise_time', 'fall_time', 'pulse_width', 'period'],
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='p', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='n', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='PULSEI',
        aliases=['pulsei', 'pulsecurrent', 'PULSECURRENT'],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='pulsed current source',
        description='Pulsed current source',
        ref_prefix='I',
        pyspice={
            'name': 'PulseCurrentSource',
            'pos': [],
            'kw': ['initial_value', 'pulsed_value', 'delay_time', 'rise_time', 'fall_time', 'pulse_width', 'period'],
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='p', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='n', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='EXPV',
        aliases=['expv', 'exponentialvoltage', 'EXPONENTIALVOLTAGE'],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='exponential voltage source',
        description='Exponential voltage source',
        ref_prefix='V',
        pyspice={
            'name': 'ExponentialVoltageSource',
            'pos': [],
            'kw': ['initial_value', 'pulsed_value', 'rise_delay_time', 'rise_time_constant', 'fall_delay_time', 'fall_time_constant'],
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='p', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='n', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='EXPI',
        aliases=['expi', 'exponentialcurrent', 'EXPONENTIALCURRENT'],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='exponential current source',
        description='Exponential current source',
        ref_prefix='I',
        pyspice={
            'name': 'ExponentialCurrentSource',
            'pos': [],
            'kw': ['initial_value', 'pulsed_value', 'rise_delay_time', 'rise_time_constant', 'fall_delay_time', 'fall_time_constant'],
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='p', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='n', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='PWLV',
        aliases=['pwlv', 'piecewiselinearvoltage', 'PIECEWISELINEARVOLTAGE'],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='piecewise linear voltage source',
        description='Piecewise linear voltage source',
        ref_prefix='V',
        pyspice={
            'name': 'PieceWiseLinearVoltageSource',
            'pos': [],
            'kw': ['values', 'repeate_time', 'delay_time',],
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='p', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='n', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='PWLI',
        aliases=['pwli', 'piecewiselinearcurrent', 'PIECEWISELINEARCURRENT'],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='piecewise linear current source',
        description='Piecewise linear current source',
        ref_prefix='I',
        pyspice={
            'name': 'PieceWiseLinearCurrentSource',
            'pos': [],
            'kw': ['values', 'repeate_time', 'delay_time',],
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='p', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='n', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='FMV',
        aliases=['fmv', 'SFFMV', 'sffmv', 'SINGLEFREQUENCYFMVOLTAGE', 'singlefrequencyfmvoltage'],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='single frequency FM modulated voltage source',
        description='Single-frequency FM-modulated voltage source',
        ref_prefix='V',
        pyspice={
            'name': 'SingleFrequencyFMVoltageSource',
            'pos': [],
            'kw': ['offset', 'amplitude', 'carrier_frequency', 'modulation_index', 'signal_frequency'],
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='p', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='n', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='FMI',
        aliases=['fmi', 'SFFMI', 'sffmi', 'SINGLEFREQUENCYFMCURRENT', 'singlefrequencyfmcurrent'],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='single frequency FM modulated current source',
        description='Single-frequency FM-modulated current source',
        ref_prefix='I',
        pyspice={
            'name': 'SingleFrequencyFMCurrentSource',
            'pos': [],
            'kw': ['offset', 'amplitude', 'carrier_frequency', 'modulation_index', 'signal_frequency'],
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='p', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='n', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='AMV',
        aliases=['amv', 'AMPLITUDEMODULATEDVOLTAGE', 'amplitudemodulatedvoltage'],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='amplitude modulated voltage source',
        description='Amplitude-modulated voltage source',
        ref_prefix='V',
        pyspice={
            'name': 'AmplitudeModulatedVoltageSource',
            'pos': [],
            'kw': ['offset', 'amplitude', 'carrier_frequency', 'modulating_frequency', 'signal_delay'],
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='p', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='n', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='AMI',
        aliases=['ami', 'AMPLITUDEMODULATEDCURRENT', 'amplitudemodulatedcurrent'],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='amplitude modulated current source',
        description='Amplitude-modulated current source',
        ref_prefix='I',
        pyspice={
            'name': 'AmplitudeModulatedCurrentSource',
            'pos': [],
            'kw': ['offset', 'amplitude', 'carrier_frequency', 'modulating_frequency', 'signal_delay'],
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='p', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='n', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='RNDV',
        aliases=['rndv', 'RANDOMVOLTAGE', 'randomvoltage'],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='random voltage source',
        description='Random voltage source',
        ref_prefix='V',
        pyspice={
            'name': 'RandomVoltageSource',
            'pos': [],
            'kw': ['random_type', 'duration', 'time_delay', 'parameter1', 'parameter2'],
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='p', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='n', func=Pin.PASSIVE, do_erc=True),
        ]),
    Part(
        name='RNDI',
        aliases=['rndi', 'RANDOMCURRENT', 'randomcurrent'],
        dest=TEMPLATE,
        tool=SKIDL,
        keywords='random current source',
        description='Random current source',
        ref_prefix='I',
        pyspice={
            'name': 'RandomCurrentSource',
            'pos': [],
            'kw': ['random_type', 'duration', 'time_delay', 'parameter1', 'parameter2'],
            'add': add_part_to_circuit,
        },
        num_units=1,
        do_erc=True,
        pins=[
            Pin(num='1', name='p', func=Pin.PASSIVE, do_erc=True),
            Pin(num='2', name='n', func=Pin.PASSIVE, do_erc=True),
        ]),
])