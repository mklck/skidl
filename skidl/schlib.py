# -*- coding: utf-8 -*-

# The MIT License (MIT) - Copyright (c) 2016-2021 Dave Vandenbout.

"""
Handles schematic libraries for various ECAD tools.
"""

from __future__ import (  # isort:skip
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from builtins import object, str

from future import standard_library
import re

from .alias import Alias
from .logger import active_logger
from .utilities import (
    filter_list,
    flatten,
    list_or_scalar,
    cnvt_to_var_name,
    opened,
)

standard_library.install_aliases()


class SchLib(object):
    """
    A class for storing parts from a schematic component library file.

    Attributes:
        filename: The name of the file from which the parts were read.
        parts: The list of parts (composed of Part objects).

    Args:
        filename: The name of the library file.
        tool: The format of the library file (e.g., KICAD).

    Keyword Args:
        attribs: Key/value pairs of attributes to add to the library.
    """

    # Keep a dict of filenames and their associated SchLib object
    # for fast loading of libraries.
    _cache = {}

    def __init__(self, filename=None, tool=None, lib_section=None, **attribs):
        """
        Load the parts from a library file.
        """

        import skidl
        from .tools import tool_modules

        if tool is None:
            tool = skidl.get_default_tool()

        # Library starts off empty of parts.
        self.parts = []

        # Attach attributes to the library.
        for k, v in list(attribs.items()):
            setattr(self, k, v)

        # If no filename, create an empty library.
        if not filename:
            pass

        # Load this SchLib with an existing SchLib object if the file name
        # matches one in the cache.
        elif filename in self._cache:
            self.__dict__.update(self._cache[filename].__dict__)

        # Otherwise, load from a schematic library file.
        else:
            try:
                # Use the tool name to find the function for loading the library.
                tool_modules[tool].load_sch_lib(self, filename, skidl.lib_search_paths[tool], lib_section=lib_section)
            except AttributeError:
                # OK, that didn't work so well...
                active_logger.raise_(
                    ValueError,
                    "Unsupported ECAD tool library: {}.".format(tool),
                )
            else:
                self.filename = filename
                # Cache a reference to the library.
                self._cache[filename] = self

    @classmethod
    def reset(cls):
        """Clear the cache of processed library files."""
        cls._cache = {}

    def add_parts(self, *parts):
        """Add one or more parts to a library."""

        from .part import TEMPLATE

        for part in flatten(parts):
            # Parts with the same name are not allowed in the library.
            if not self.get_parts_by_name(
                part.name, be_thorough=False, allow_failure=True
            ):
                self.parts.append(part.copy(dest=TEMPLATE))
                # Place a pointer to this library into the added part.
                self.parts[-1].lib = self
        return self

    __iadd__ = add_parts

    def get_parts(self, use_backup_lib=True, **criteria):
        """
        Return parts from a library that match *all* the given criteria.

        Keyword Args:
            criteria: One or more keyword-argument pairs. The keyword specifies
                the attribute name while the argument contains the desired value
                of the attribute.

        Returns:
            A list of Parts that match all the criteria.
        """

        import skidl

        parts = filter_list(self.parts, **criteria)
        if not parts and use_backup_lib and skidl.QUERY_BACKUP_LIB:
            try:
                backup_lib_ = skidl.load_backup_lib()
                parts = backup_lib_.get_parts(use_backup_lib=False, **criteria)
            except AttributeError:
                pass
        return parts

    def get_parts_quick(self, name):
        """Do a quick search for a part name or alias."""
        return [prt for prt in self.parts if prt.aliases == name]

    def get_parts_by_name(
        self,
        name,
        be_thorough=True,
        allow_multiples=False,
        allow_failure=False,
        partial_parse=False,
    ):
        """
        Return a Part with the given name or alias from the part list.

        Args:
            name: The part name or alias to search for in the library.
            be_thorough: Do thorough search, not just simple string matching.
            allow_multiples: If true, return a list of parts matching the name.
                If false, return only the first matching part and issue
                a warning if there were more than one.
            allow_failure: Return None if no matches found. Issue no errors/warnings.
            partial_parse: If true, don't fully parse any parts that are found.

        Returns:
            A list of Parts that match all the criteria.
        """

        # Start with a simple search for the part name.
        names = Alias(name, name.lower(), name.upper())
        parts = self.get_parts_quick(names)

        # Simple search failed, so try the more thorough search method.
        if not parts and be_thorough:
            parts = self.get_parts(aliases=name)

        # No parts found, so signal an error.
        if not parts and not allow_failure:
            message = "Unable to find part {} in library {}.".format(
                name, getattr(self, "filename", "UNKNOWN")
            )
            active_logger.raise_(ValueError, message)

        if len(parts) > 1 and not allow_multiples:
            message = "Found multiple parts matching {}. Selecting {}.".format(
                name, parts[0].name
            )
            active_logger.warning(message)
            parts = parts[0:1]  # Just keep the first part.

        # Do whatever parsing was requested for the found parts.
        for part in parts:
            part.parse(partial_parse)

        return parts

    def __getitem__(self, id):
        """Get part by name or alias."""
        return list_or_scalar(self.get_parts_by_name(id))

    def __str__(self):
        """Return a list of the part names in this library as a string."""
        return "\n".join(["{}: {}".format(p.name, p.description) for p in self.parts])

    __repr__ = __str__

    def export(self, libname, file_=None, tool=None):
        """
        Export a library into a file.

        Args:
            libname: A string containing the name of the library.
            file_: The file the library will be exported to. It can either
                be a file object or a string or None. If None, the file
                will be the same as the library name with the library
                suffix appended.
            tool: The CAD tool library format to be used. Currently, this can
                only be SKIDL.
        """

        def prettify(s):
            """Breakup and indent library export string."""
            s = re.sub(r"(Part\()", r"\n        \1", s)
            s = re.sub(r"(Pin\()", r"\n            \1", s)
            return s

        import skidl

        from .tools import SKIDL

        if tool is None:
            tool = SKIDL

        if not file_:
            file_ = libname + skidl.lib_suffixes[tool]

        export_str = "from skidl import Pin, Part, Alias, SchLib, SKIDL, TEMPLATE\n\n"
        export_str += "SKIDL_lib_version = '0.0.1'\n\n"
        part_export_str = ",".join([p.export() for p in self.parts])
        export_str += "{} = SchLib(tool=SKIDL).add_parts(*[{}])".format(
            cnvt_to_var_name(libname), part_export_str
        )
        export_str = prettify(export_str)
        with opened(file_, "w") as f:
            f.write(export_str)

    def __len__(self):
        """
        Return number of parts in library.
        """
        return len(self.parts)
