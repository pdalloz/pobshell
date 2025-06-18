"""Pobshell imports this file at startup.

Edit it to change what's reported by 'ls -l' and 'ls -x' commands.

Additionally define here: Filtersets that hide some objects from listings, and Prunesets that exclude objects
from being walked by the find command.

Pobshell PYEXPR evaluation with eval, rooteval, printpy commands and find's --matchpy or --printpy options
have access to the names in this module if Pobshell setting global_ns has the value 'user'
    'set global_ns user'

    E.g. This user_defs.py module imports inspect, so inpect module functions can be used if 'global_ns' is 'user'
        (NB Just prints the source file line number for each matched object)
        find . --printpy inspect.getsourcelines(self)[1] --isroutine



"""

from inspect import (isabstract, isasyncgen, isasyncgenfunction, isawaitable, isbuiltin, isclass,
                     iscode, iscoroutine, iscoroutinefunction, isdatadescriptor, isframe, isfunction,
                     isgenerator, isgeneratorfunction, isgetsetdescriptor, ismemberdescriptor, ismethod,
                     ismethoddescriptor, ismodule, isroutine, istraceback)

import inspect

from pprint import saferepr
import fnmatch


if hasattr(inspect, 'ismethodwrapper'):
    from inspect import ismethodwrapper

# BLACK       CYAN             GREEN            LIGHT_CYAN       LIGHT_GREEN      LIGHT_RED        MAGENTA    WHITE
# BLUE        DARK_GRAY        LIGHT_BLUE       LIGHT_GRAY       LIGHT_MAGENTA    LIGHT_YELLOW     RED        YELLOW


contentkey_delimiter = "`"  # Haven't tested changing this

# set available_filters to a range of utility functions    ----------------------------------------------------
#   The names must all begin with 'is' and they must return True or False on any python object
#   E.g. the inspect functions isroutine, ismodule, isclass
#     and the pydoc utility function isdata
#   Inspection commands and find command will automatically have these filters added to their arg list parsers
#     and negated versions prefixed 'nis-' will also be
#   Negative versions of each will also be
#   Feel free to import whatever you need here and create more is* boolean filters for find criteria,
#     E.g. find --isdata
#     or infocmd filters
#     E.g.   ls -l --nisbuiltin

from pydoc import isdata

available_filters = {'isdata': isdata}
predicate_funcs = [(func_name, func) for (func_name, func)
                   in inspect.getmembers(inspect, inspect.isfunction) if func_name.startswith('is')]
available_filters.update(predicate_funcs)


# Define named prunesets: CODE, DATA, ..    ----------------------------------------------------

SEARCH_MODES = {
    "DATA": {
        "prune_paths": ['*/sys/modules'],
        "prune_prefixes": ['_'],
        "prune_types": [int, float, str, bool, ...],
        'DATA': [
            'bool', 'float', 'int', 'complex', 'str', 'bytes',
            'bytearray', 'memoryview',
            # skip properties', staticmethods, method_wrappers
            'property', 'staticmethod', 'method-wrapper', 'wrapper_descriptor',
            # but allow list/tuple/dict, because might have interesting nested objects
        ],
        "prune_predicates": [isroutine, isdatadescriptor],
    },
    "CODE": {
        "prune_paths": ['*/importlib/*', '*/__dir__/*'],
        "prune_prefixes": ['_'],
        "prune_types": [int, float, str, bool, ...],
        "prune_predicates": [isbuiltin, ismethoddescriptor],
    },
    # ...
}


def CODE(pn):
    """Focus on code objects (prune non-code) """
    return (type(pn.obj).__name__ in {'bool', 'float', 'int', 'complex', 'list', 'str', 'bytes',
                                      'bytearray', 'memoryview', 'tuple', 'dict', 'set',
                                      'frozenset', 'staticmethod', 'method-wrapper', 'wrapper_descriptor'}
            or any(fnmatch.fnmatchcase(pn.abspath, pattern) for pattern in {'*/importlib/*', '*/__dir__/*'})
            or inspect.isbuiltin(pn.obj) or inspect.ismethoddescriptor(pn.obj)
            # or inspect.isdatadescriptor(pn.obj)
            )


def DATA(pn):
    """Focus on data objects (prune non-data)"""
    # A prune function that returns True for paths we should prune when searching for DATA
    return (type(pn.obj).__name__ in {'bool', 'float', 'int', 'complex', 'str', 'bytes',
                                      'bytearray', 'memoryview', 'property', 'staticmethod',
                                      'method-wrapper', 'wrapper_descriptor'}
            or any(fnmatch.fnmatchcase(pn.abspath, pattern) for pattern in {'*/sys/modules', '*/__dir__/*'})
            or inspect.isroutine(pn.obj) or inspect.isdatadescriptor(pn.obj)
            # or inspect.ismethoddescriptor(pn.obj) or inspect.isgetsetdescriptor(pn.obj)
            # or inspect.ismemberdescriptor(pn.obj) or inspect.ismethodwrapper(pn.obj)
            )


def BASIC(pn):
    """Generic pruning of unhelpful paths, such as /__dir__/"""
    # A prune function that returns True for paths we should prune when searching for anything
    return any(fnmatch.fnmatchcase(pn.abspath, pattern) for pattern in {'*/sys/modules', '*/__dir__/*'})


prunesets = {'CODE': CODE, 'DATA': DATA, 'BASIC': BASIC}

# Define map setting for each pruneset
# I.e. CODE pruneset calls 'map attributes' and DATA calls 'map everything'
pruneset_maps = {'CODE': 'attributes', 'DATA': 'everything', 'BASIC': None}


# Set color scheme and output styling    ----------------------------------------------------

themes = {
    "dark": {
        "prompt": "MAGENTA",
        "path": "WHITE",
        "type": "CYAN",
        "value": "LIGHT_GREEN",
        "banner": "WHITE",
        "bg": "dark",
        "warning": "RED",
    },
    "light": {
        "prompt": "MAGENTA",
        "path": "BLACK",
        "type": "CYAN",
        "value": "BLUE",
        "banner": "GREEN",
        "bg": "light",
        "warning": "RED",
    },
}

lsl_style_list = ['path', 'type', 'value']  # styles from above themes above to apply to lsl_func output


# Define what "ls -l"  does    ----------------------------------------------------

def lsl_func(pn, path_func, is_verbose):
    # defines output for "ls -l" (one-line column oriented output)
    #   First column is expected to be the abspath or name, not sure if absolutely necessary though
    #     path_func is the function PV.output_infos uses to format path or name for column 0
    #   First column stretches to fit, middle columns are fixed size, and last column uses what space is left
    #   pn.obj is the object at the path, truncate this to 300 chars as ls -l listings are one-line
    #    - to speed up column width formatting later in output_infos call to RunningTable.row
    return [path_func(pn), pn.typename, saferepr(pn.obj)[:300].replace('\n', ' ')]


# Defines the list of commands applied by "ls -x".  First one has to be "ls -l" I think?
lsx_cmds = [
    "ls -l",
    "type -1",
    "predicates -1",
    "abcs -1",
    "memsize -1",
    "doc -1",
    "pydoc -1",
    "mro -1",
    "cat -1",
    "signature -1",
    "module -1",
    "filepath -1",
    "pypath -1",
    "id -1",
    "which -1"
]
