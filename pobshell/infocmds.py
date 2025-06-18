# TODO Rename INFOCMD objects to match the new name 'Inspection commands' in documentation
#  and _INFOFILTERS to something FILTER related for 'Inspection commands'

import re
import fnmatch
from contextlib import nullcontext
from typing import Callable
import argparse
import cmd2
from cmd2 import ansi

from .common import (temporary_setting, NoSuchInfo, MissingInfoOptions, PobPrefs)
import textwrap

# Command categories for cmd2
CMD_CAT_POBSHELL_TESTING = '0 - Pobshell testing'   # Hidden if PobPrefs.DEBUG is False
CMD_CAT_PATH_MANIPULATION = '1 - Navigation'
CMD_CAT_LIST_DIR = '2 - List & search'
CMD_CAT_INFO = '3 - Inspection'
CMD_CAT_MAP = '4 - Mapping'
CMD_CAT_PYTHON = '5 - Python evaluation'
CMD_CAT_UTILS = '6 - Utility'
CMD_CAT_SCRIPTING = '7 - Scripts, aliases, and OS shell'
CMD_CAT_UNCATEGORIZED = '8 - Uncategorized'

# recipes for argparse.add_argument, used to build a parser for Inspection methods (do_cat, do_doc, do_ls, ...)
STANDARD_ARGS ={
    'TARGET': (('TARGET', ), {'nargs': argparse.OPTIONAL,
                               'help': 'Specify the target (path, name, or glob pattern)',
                               'suppress_tab_hint': True}),
    'PYEXPR': (('PYEXPR', ), {'type': str, 'help': 'Python expression to evaluate'}),
    '-a': (('-a', '--all'), {'action': 'store_true', 'help': 'Include hidden members'}),
    '-1': (('-1', '--oneline'), {'action': 'store_true', 'help': 'Single line format, truncate output to one line'}),
    '-l': (('-l', '--long'), {'action': 'store_true', 'help': 'Long format, each line prefixed with name or path'}),
    '-x': (('-x', '--xtralong'), {'action': 'store_true', 'help': 'Extended multiline output'}),
    '-n': (('-n', '--numlines'), {'type': int, 'metavar': 'N', 'help': 'Truncate output to N lines per member'}),
    '-L': (('-L', '--LIMIT'), {'type': int, 'metavar': 'N', 'help': 'Stop after reporting N members'}),
    '-u': (('-u', '--unstyled'), { 'action': 'store_true', 'help': 'Disable ANSI styling in output'}),
    '-p': (('-p', '--paged'), {'action':'store_true', 'help': 'Paginate the output for easier reading'}),
    '-v': (('-v', '--verbose'), {'action': 'store_true', 'help': 'Output full Pobshell paths'}),
    '-P': (('-P', '--PYPATH'), {'action': 'store_true', 'help': 'Output Python paths [experimental]'}),
    '-q': (('-q', '--quiet'), {'action': 'store_true', 'help': 'Suppress name and path information in the output'}),
    '-r': (('-r', '--regex'), {'action': 'store_true', 'help': 'Treat all PATTERNs as regular expressions (except TARGET)'}),
    '-i': (('-i', '--ignore-case'), {'action': 'store_true', 'help': 'Use case-insensitive matching for PATTERNs (except TARGET)'}),
    '-e': (('-e', '--enumerate'), {'action': 'store_true', 'help': 'Enumerate output to support later reference with "$N"'}),
    '--missing': (('--missing',), {'choices': ['skip', 'blank', 'message'], 'help': 'Specify how missing information is handled'}),
    '--map': (('--map',), {'choices': PobPrefs.map_option_names, 'help': 'Apply a temporary mapping setting'}),
}

# argparser Specs for --FILTER args for Inspection commands
INFOCMD_ARGS = [
    (('--name',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    (('--cat',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    (('--doc',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    (('--pydoc',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    (('--filepath',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    (('--memsize',), {'type': str, 'metavar': 'MEMSIZE_EXPR', 'help': 'SUPPRESS'}),
    (('--id',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    (('--mro',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    (('--abcs',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    (('--predicates',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    (('--module',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    (('--pypath',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    (('--signature',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    (('--type',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    (('--typename',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    (('--repr',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    (('--str',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    # (('--value',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    (('--abspath',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    (('--which',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),

    # negatives ------------
    (('--nname',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    (('--ncat',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    (('--ndoc',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    (('--npydoc',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    (('--nfile',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    (('--nid',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    (('--nmro',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    (('--nabcs',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    (('--npredicates',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    (('--npypath',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    (('--nsignature',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    (('--ntype',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    (('--ntypename',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    (('--nstr',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    (('--nrepr',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    # (('--nvalue',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    (('--nabspath',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),
    (('--nwhich',), {'type': str, 'metavar': 'PATTERN', 'help': 'SUPPRESS'}),

    # Position the following 2 items at end of list, because Pobiverse.do_find
    #   excludes them from auto argparse argument creation loop, in order to bespoke help text
    #   by position in list
    (('--matchpy',), {'type': str, 'metavar': 'PYEXPR', 'help': 'SUPPRESS'}),
    (('--noraise',), {'action': 'store_true', 'help': 'SUPPRESS'})
]

# List of filters available for Inspection commands such as "ls", "cat", "doc", ..
# the list is updated in update_INFOFILTERS function below,
#   with extra filters imported from PobPrefs.available_filters
#   (called by Pobiverse.__init__ when PobPrefs.available_filters have been loaded)

# These identify the info commands that find and Inspection commands support as match criteria
#   NB _INFOFILTERS has Inspection-funcs listed in order of speed of execution & likelihood of rejection
#     ie beginning of the tuple are the filters which are fast to retrieve and return short strings
#     for fast match tests

INFOFILTERS = None
_INFOFILTERS = ['name', 'id', 'type', 'typename', 'str', 'repr', 'signature', 'abspath', 'module', 'mro', 'predicates',
                'abcs', 'filepath', 'module', 'which', 'doc', 'pypath', 'cat', 'memsize', 'pydoc']   # NB 'matchpy' is hardcoded separately

def update_INFOFILTERS():
    global INFOFILTERS, INFOCMD_ARGS
    if INFOFILTERS is None:
        INFOFILTERS = _INFOFILTERS
    INFOFILTERS.extend(PobPrefs.available_filters.keys())
    for k in PobPrefs.available_filters.keys():
        new_arg = (('--' + k,), {'action': 'store_true', 'help': 'SUPPRESS'})
        INFOCMD_ARGS.insert(-2, new_arg)
        new_neg_arg = (('--n' + k,), {'action': 'store_true', 'help': 'SUPPRESS'})
        INFOCMD_ARGS.insert(-2, new_neg_arg)


# set up arg keys strings as variables, to make it easy to find uses and rename flags
#   Seemed a good idea at the time, but reference data in this file uses hard coded strings rather than the variables
#   TODO Remove these and just use hard coded strings?
argstr_oneline = 'oneline'
argstr_numlines = 'numlines'
argstr_LIMIT = 'LIMIT'
argstr_paged = 'paged'
argstr_verbose = 'verbose'
argstr_pypath = 'PYPATH'  # upper case '--PYPATH/-P' is an output option, lower case '--pypath PATTERN' is a filter
argstr_unstyled = 'unstyled'
argstr_quiet = 'quiet'
argstr_TARGET = 'TARGET'
argstr_all = 'all'
argstr_regex = 'regex'
argstr_ignore_case = 'ignore_case'
argstr_matchpy = 'matchpy'
argstr_asizeof = 'memsize'
argstr_printpy = 'printpy'
argstr_pyexpr = 'PYEXPR'
argstr_skip = 'skip'
argstr_blank = 'blank'
argstr_message = 'message'
argstr_long = 'long'
argstr_xtralong = 'xtralong'
argstr_enumerate = 'enumerate'


# Specify which basic OPTIONS, i.e. entries in INFOCMD_ARGS, are applicable to each inspection command
INFOCMD_SPECS = {
    'abcs': {'eval': lambda x: x.abcs,
             'args': ['-a', '-1', '-n', '-l', '-L', '-v', '-P', '-u', '-q', '-r', '-i', '-e', '--missing', '--map', 'TARGET'],
             'category': CMD_CAT_INFO,
             '__doc__': 'Abstract base classes from collections.abc'},

    'memsize': {'eval': lambda x: x.memsize,
                'args': ['-a', '-1', '-n', '-l', '-L', '-v', '-P', '-u', '-q', '-r', '-i', '-e', '--missing', '--map', 'TARGET'],
                'category': CMD_CAT_INFO,
                '__doc__': 'Total memory size of object and members, using pympler.asizeof'},

    'cat': {'eval': lambda x: x.cat,
            'args': ['-a', '-1', '-n', '-l', '-L', '-v', '-P', '-u', '-q', '-r', '-i', '-e', '-p', '--missing', '--map', 'TARGET'],
            'category': CMD_CAT_INFO,
            '__doc__': 'Source code of object using inspect.getsource'},

    'doc': {'eval': lambda x: x.doc,
            'args': ['-a', '-1', '-n', '-l', '-L', '-v', '-P', '-u', '-q', '-r', '-i', '-e', '-p', '--missing', '--map', 'TARGET'],
            'category': CMD_CAT_INFO,
            '__doc__': 'Documentation string via __doc__ or inspect.getdoc'},

    'filepath': {'eval': lambda x: x.filepath,
                 'args': ['-a', '-1', '-n', '-l', '-L', '-v', '-P', '-u', '-q', '-r', '-i', '-e', '--missing', '--map', 'TARGET'],
                 'category': CMD_CAT_INFO,
                 '__doc__': 'File where the object was defined, from inspect.getfile'},

    'id': {'eval': lambda x: x.id,
           'args': ['-a', '-1', '-n', '-l', '-L', '-v', '-P', '-u', '-q', '-r', '-i', '-e', '--missing', '--map', 'TARGET'],
           'category': CMD_CAT_INFO,
           '__doc__': 'Unique identifier of the object (id)'},

    'ls': {'eval': None, # Hard coded in output_infos
           'args': ['-l', '-x', '-a', '-1', '-n', '-L', '-v', '-P', '-u', '-r', '-i', '-e', '--missing', '--map', 'TARGET'],
           'category': CMD_CAT_LIST_DIR,
           '__doc__': 'List members of object'},

    'mro': {'eval': lambda x: x.mro,
            'args': ['-a', '-1', '-n', '-l', '-L', '-v', '-P', '-u', '-q', '-r', '-i', '-e', '--missing', '--map', 'TARGET'],
            'category': CMD_CAT_INFO,
            '__doc__': 'Method resolution order (inspect.getmro)'},

    'pathinfo': {'eval': None,  # Hard coded in output_infos
                 'args': ['-a', '-1', '-n', '-l', '-L', '-v', '-P', '-u', '-r', '-i', '--missing', '--map', 'TARGET'],
                 'category': CMD_CAT_LIST_DIR,
                 '__doc__': 'List each component of path using ls -x'},

    'predicates': {'eval': lambda x: x.predicates,
                   'args': ['-a', '-1', '-n', '-l', '-L', '-v', '-P', '-u', '-q', '-r', '-i', '-e', '--missing', '--map', 'TARGET'],
                   'category': CMD_CAT_INFO,
                   '__doc__': 'Predicate functions that return True, from inspect.is* and pydoc.isdata'},

    'printpy': {'eval': None,   # Hard coded in make_infomethod / imethod
                'args': ['-a', '-1', '-n', '-l', '-L', '-v', '-P', '-u', '-q', '-r', '-i', '-e', '-p', '--missing',
                         '--map', 'PYEXPR', 'TARGET'],
                'category': CMD_CAT_PYTHON,
                '__doc__': 'Evaluate and print Python expression in context of TARGET object',
                },

    'pydoc': {'eval': lambda x: x.pydoc,
              'args': ['-a', '-1', '-n', '-l', '-L', '-v', '-P', '-u', '-q', '-r', '-i', '-e', '-p', '--missing', '--map', 'TARGET'],
              'category': CMD_CAT_INFO,
              '__doc__': 'Auto-generated documentation using pydoc'},

    'pypath': {'eval': lambda x: x.pypath,
               'args': ['-a', '-1', '-n', '-l', '-L', '-v', '-P', '-u', '-q', '-r', '-i', '-e', '--missing', '--map', 'TARGET'],
               'category': CMD_CAT_PATH_MANIPULATION,
               '__doc__': "Python path of object: Translate '/' to '.' and '[]' [experimental]"},

    'signature': {'eval': lambda x: x.signature,
                  'args': ['-a', '-1', '-n', '-l', '-L', '-v', '-P', '-u', '-q', '-r', '-i', '-e', '--missing', '--map', 'TARGET'],
                  'category': CMD_CAT_INFO,
                  '__doc__': 'Function signature from inspect.signature'},

    'type': {'eval': lambda x: x.type,
             'args': ['-a', '-1', '-n', '-l', '-L', '-v', '-P', '-u', '-q', '-r', '-i', '-e', '--missing', '--map', 'TARGET'],
             'category': CMD_CAT_INFO,
             '__doc__': 'Type of the object'},

    'typename': {'eval': lambda x: x.typename,
                 'args': ['-a', '-1', '-n', '-l', '-L', '-v', '-P', '-u', '-q', '-r', '-i', '-e', '--missing', '--map', 'TARGET'],
                 'category': CMD_CAT_INFO,
                 '__doc__': 'Name of the object’s type (type.__name__)'},

    'pprint': {'eval': lambda x: x.pprint,
               'args': ['-a', '-1', '-n', '-l', '-L', '-v', '-P', '-u', '-q', '-r', '-i', '-e', '-p', '--missing', '--map', 'TARGET'],
               'category': CMD_CAT_INFO,
                '__doc__': 'Pretty-printed object value via pprint'},

    'str': {'eval': lambda x: x.strval,
              'args': ['-a', '-1', '-n', '-l', '-L', '-v', '-P', '-u', '-q', '-r', '-i', '-e', '-p', '--missing', '--map', 'TARGET'],
              'category': CMD_CAT_INFO,
              '__doc__': 'str() representation of object value'},

    'repr': {'eval': lambda x: x.reprval,
              'args': ['-a', '-1', '-n', '-l', '-L', '-v', '-P', '-u', '-q', '-r', '-i', '-e', '-p', '--missing', '--map', 'TARGET'],
              'category': CMD_CAT_INFO,
              '__doc__': 'saferepr() representation of object value'},

    'which': {'eval': lambda x: x.which,
              'args': ['-a', '-1', '-n', '-l', '-L', '-v', '-P', '-u', '-q', '-r', '-i', '-e', '--missing', '--map', 'TARGET'],
              'category': CMD_CAT_INFO,
              '__doc__': 'Defining class for a method or descriptor'},

    'module': {'eval': lambda x: x.module,
               'args': ['-a', '-1', '-n', '-l', '-L', '-v', '-P', '-u', '-q', '-r', '-i', '-e', '--missing', '--map', 'TARGET'],
               'category': CMD_CAT_INFO,
               '__doc__': 'Module that defines the object (inspect.getmodule)'},

    'dir': {'eval': lambda x: str(dir(x.obj)),
            'args': ['-a', '-1', '-n', '-l', '-L', '-v', '-P', '-u', '-q', '-r', '-i', '-e', '--missing', '--map', 'TARGET'],
            'category': CMD_CAT_POBSHELL_TESTING,
            '__doc__': "dir(object) — for testing; use 'ls' instead"},
}



class HideArgumentHelpFormatter(argparse.RawTextHelpFormatter):
    """
    Custom formatter to hide certain arguments from help text and handle newlines.
    """
    def _format_action(self, action):
        if action.option_strings == ['-h', '--help']:
            return ''
        if action.help == 'SUPPRESS':
            return ''
        return super()._format_action(action)

    def _split_lines(self, text, width):
        # If the text contains explicit newline characters, split on them first
        if "\n" in text:
            lines = []
            for line in text.splitlines():
                lines.extend(argparse.HelpFormatter._split_lines(self, line, width))
            return lines
        else:
            return argparse.HelpFormatter._split_lines(self, text, width)


def make_match_func(info_filter: str, pattern: str, negated: bool, args) -> Callable:
    """
    Construct a lambda function that
        tests --info_func return strings against a user pattern,
        tests --matchpy's PYEXPR for truthiness
        tests --is* functions for truthiness
    Used to filter lists of pobnodes.

    Args:
        info_filter: Name of the info function to filter by, e.g., 'cat', 'file', 'predicates', or 'matchpy'.
        pattern: Glob or regex string to match, or Python code if info_name is 'matchpy'.
        negated: If True, the criteria requires "NOT match".
        args: Additional arguments for regex and case sensitivity.

    Returns:
        A callable match function.
    """
    if info_filter == argstr_matchpy:
        # For 'matchpy', evaluate the pattern as a Python expression
        return lambda pn: is_pyexpr_match(pn, pyexpr=pattern, noraise=args.noraise)
    elif info_filter == argstr_asizeof:
        return lambda pn: pn.memsize_comparison(pattern)
    elif info_filter.startswith('is'):
        if negated:
            return lambda pn: not PobPrefs.available_filters[info_filter](pn.obj)
        else:
            return lambda pn: PobPrefs.available_filters[info_filter](pn.obj)

    # Convert glob pattern to regex if args don't specify that pattern is regex already
    if not getattr(args, argstr_regex, None):
        pattern = fnmatch.translate(pattern)  # Converts glob pattern to regex

    # Compile the regex with or without case sensitivity
    regex_flags = re.IGNORECASE if getattr(args, argstr_ignore_case, None) else 0
    compiled_pattern = re.compile(pattern, regex_flags)

    # apply match or search behavior
    search_func = compiled_pattern.search if getattr(args, argstr_regex, None) else compiled_pattern.match

    # Return a lambda function to evaluate matches
    return lambda pn: is_info_match(pn, info_filter, search_func, negated)



def is_info_match(pn: object, info_name: str, search_func: Callable, negated: bool) -> bool:
    """
    Retrieve the value of pn's info_name property and test match.

    Args:
        pn: The object to test
        info_name: The name of the property to retrieve.
        search_func: A callable to test the match.
        negated: If True, negates the match result.

    Returns:
        A boolean indicating whether the condition is met.
    """
    # TODO: Replace this kludged map of info_name -> PobNode property
    if info_name == 'str':
        info_name = 'strval'
    elif info_name == 'repr':
        info_name = 'reprval'

    # Temporarily disable prettification so ansi codes won't break string matching for infos
    #   also prevents return of NoSuchInfo objects
    with temporary_setting('prettify_infos', False):
        info_result = getattr(pn, info_name, None)

    # empty result string or NoSuchInfo object automatically fails the match
    if not info_result or isinstance(info_result, NoSuchInfo):
        return negated

    # Apply the search function and return the result
    return not search_func(info_result) if negated else search_func(info_result)


def is_pyexpr_match(pn: object, pyexpr: callable, noraise: bool) -> bool:
    """Evaluate pyexpr in the namespace of pn, returning the result."""
    with temporary_setting('prettify_infos', False):
        try:
            return pn.eval_PYEXPR(pyexpr, expecting_eval=True)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            if not noraise:
                raise NoSuchInfo(f'{argstr_matchpy} exception at path: {pn.abspath}: "{str(e)}"')


def extract_filter_criteria(args, filters, for_show=False):
    """
    Extract filtering criteria from args.

    :param args: The argparse namespace.
    :param filters: A list of filter names (e.g. INFOFILTERS).
    :param for_show: If True, then we’re processing for a “show” command,
                     and we return None for filters that are meant to be removed.
    :return: A dict mapping filter names (with negation prefix) to either
             a tuple (pattern, match_lambda) or None.
    """
    # Fudge to add 'matchpy' back into INFOCMD_ARGS (Not sure why it's not in there)
    #   TODO Look at making matchpy an entry in INFOCMD_ARGS
    all_filters = filters + ['matchpy']
    criteria = {}
    for filt in all_filters:
        # Loop through both normal and negated versions.
        for neg in (False, True):
            arg_name = ('n' if neg else '') + filt
            # Get the pattern to filter by
            pattern = getattr(args, arg_name, None)
            if for_show:
                if pattern is True:
                    criteria[arg_name] = None  # Flag for removal
            elif pattern is not None and pattern is not False:
                # pattern is not None and pattern is not False means
                criteria[arg_name] = (pattern, make_match_func(filt, pattern, neg, args))

    return criteria



def make_exclude_func(args, persistent_filter_func):
    # args: an arg from argparse after contentkeys are recovered
    # returns: a function evaluating the --INFOFILTER arguments
    #   including --matchpy and the persistent filterset, PV._nolist_func
    #   NB Doesn't handle pattern matching for TARGET pattern, that's done by report_infos
    filters_dict = extract_filter_criteria(args, INFOFILTERS, for_show=False)
    match_funcs = [func for (pat, func) in filters_dict.values() if func is not None]

    # match logic is: Exclude pobnodes that don't match all required criteria
    #   or are in persistent filterset (unless argument "-a" says include them)
    if getattr(args, argstr_all, None):
        def exclude_func(pn):
            try:
                return not all(mf(pn) for mf in match_funcs)
            except (TypeError, ValueError):  # Some objects raise exception on conversion to bool (e.g. pandas NA)
                return True
    else:
        def exclude_func(pn):
            try:
                # -a option wasn't used, so filter should use persistent_filter_func to exclude hidden objs too
                return not all(mf(pn) for mf in match_funcs) or persistent_filter_func(pn)
            except (TypeError, ValueError):   # Some objects raise exception on conversion to bool (e.g. pandas NA)
                return True
    return exclude_func


def make_argparser(info_name, pobiverse):
    # Create the argument parser for an Inspection command method
    #   input: info_name
    #   output: parser
    #  NB Called by PV.__init__ at Pobiverse init, which calls make_infomethod
    parser = cmd2.Cmd2ArgumentParser(
        prog=info_name,
        usage=(f'{info_name} [BASIC OPTIONS] [FLAG FILTERS] [PATTERN-MATCH FILTERS] [NEGATED FILTERS] [TARGET]'
               if not info_name == 'printpy'
               else
               f'{info_name} PYEXPR [BASIC OPTIONS] [FLAG FILTERS] [PATTERN-MATCH FILTERS] [NEGATED FILTERS] [TARGET]'),
        formatter_class=HideArgumentHelpFormatter,
        description=INFOCMD_SPECS[info_name]['__doc__'],
        epilog=("NEGATED FILTERS: Negate filters by adding n, e.g. --nisdata, --nabspath PATTERN\n")
    )
    basic_group = parser.add_argument_group(title="Basic options", description="")
    # create argparser arguments from 'args' list of info_name entry in INFOCMD_SPECS
    for arg in INFOCMD_SPECS[info_name]['args']:
        arg_names, argparser_spec = STANDARD_ARGS[arg]
        if arg == argstr_TARGET:
            argparser_spec['completer'] = pobiverse.ns_path_complete
        basic_group.add_argument(*arg_names, **argparser_spec)

    # Add the flag args
    flag_desc = ',  '.join(arg_names[0] for arg_names, _ in INFOCMD_ARGS
                           if arg_names[0].startswith('--is'))

    flag_filter_group = parser.add_argument_group(
        title="Flag filters",
        description=(
                # "\n"
                "Filter results by is* functions. These filters don't take a pattern \n"
                    + textwrap.fill(flag_desc, width=80))
        )

    # flag_filter_group.add_argument(*args, **kwargs)
    for arg_names, arg_specs in INFOCMD_ARGS:
        if not (arg_names[0].startswith('--is') or arg_names[0].startswith('--nis')):
            continue
        flag_filter_group.add_argument(*arg_names, **arg_specs)

    # pattern match args
    pattern_filter_group = parser.add_argument_group(
        title="Pattern-match filters",
        description=(
            # "\n"
            "Restrict results to objects whose characteristics match PATTERN\n"            
            "  PATTERNs are matched with glob wildcards '*' and '?' unless '-r' option is used\n"
            "    except --memsize which requires PATTERNs like '>10000' or '==8' '\n"
            "\n"
            "--name (object name), --cat (source code), --doc (docstring), --repr (repr(obj)),\n"
            "--str (str(obj)), --type (type(obj)), --typename (type(obj).__name__),\n"
            "--abspath (pobshell path), --abcs (ABC interfaces)\n"
            "\n"
            "--pydoc (pydoc content), --filepath (path of defining file),\n"
            "--id (object ID), --mro (MRO tuple), --which (defining class for method).\n"
            "--signature (callable signature), --predicates (inspect.is* functions)\n"
        )
    )
    for arg_names, kwarg_names in INFOCMD_ARGS:
        if arg_names[0].startswith('--is') or arg_names[0].startswith('--nis'):
            continue
        pattern_filter_group.add_argument(*arg_names, **kwarg_names)
    return parser


def make_infomethod(info_name, pobiverse):
    # Return a function implementing Inspection command whose name is info_name
    #   - A function suitable for use as a do_* method of pobmain.Pobiverse
    # The function, 'imethod', declared here implements most Pobshell Inspection commands
    #   imethod is assigned to several distinct Pobiverse do_* methods, under different names
    #       and wrapped in an individual argparser instance with bespoke helptext
    #   - note the `self` argument that references the Pobiverse instance when the method is called

    def imethod(self, args):
        self.recover_contentkey_args(args)

        exclude_func = make_exclude_func(args, self._nolist_func)

        # set the eval_func
        if info_name == argstr_printpy:
            printpy_expr = getattr(args, argstr_pyexpr, None)
            eval_func = lambda x, pyexpr=printpy_expr: str(x.eval_PYEXPR(pyexpr, expecting_eval=True, noraise=args.noraise))
        else:
            eval_func = INFOCMD_SPECS[info_name]['eval']

        # Use missing_info_pref from supplied argument if provided, else the current settings
        missing_info_pref = missing_info_options.get(args.missing, PobPrefs.missing)
        temp_map_setting = getattr(args, 'map', None)

        # output the infos
        context = self.stacked_command(PobPrefs.map_repr()) if temp_map_setting is not None else nullcontext()

        with context:  # reset to current map after temporary map setting below
            if temp_map_setting:
                self.onecmd_plus_hooks(f'''map -q {temp_map_setting}''', add_to_history=False)

            with temporary_setting('missing', missing_info_pref):
                with temporary_setting('prettify_infos', True):
                    if getattr(args, argstr_unstyled, True):
                        with temporary_setting('allow_style', ansi.AllowStyle.NEVER, self):
                            with temporary_setting('null_separator', False, PobPrefs):
                                self.output_infos(info_name, args, exclude_func, eval_func)
                                # output = infocmd_func(pn)
                    else:
                        self.output_infos(info_name, args, exclude_func, eval_func)


    # Hard coded missing_info_options
    missing_info_options = {argstr_skip: MissingInfoOptions.skip_item,
                            argstr_blank: MissingInfoOptions.empty_string,
                            argstr_message: MissingInfoOptions.exception_string}

    parser = make_argparser(info_name, pobiverse)

    # Decorate and categorize the method
    imethod.__name__ = f'do_{info_name}'   # required by cmd2.with_argparser
    imethod.__qualname__ = f'Pobiverse.do_{info_name}'   # required by cmd2.with_argparser
    argparsed_method = cmd2.with_argparser(parser)(imethod)
    argparsed_method.__name__ = imethod.__name__
    argparsed_method.__qualname__ = imethod.__qualname__
    cmd2.categorize(argparsed_method, INFOCMD_SPECS[info_name]['category'])
    return argparsed_method

