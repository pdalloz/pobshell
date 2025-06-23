# -*- coding: utf-8 -*-
"""
pobmain.py - Main Module for the Pobshell Project

This module provides core functionality for Pobshell, an interactive CLI
that exposes Python object hierarchies in a filesystem-like manner. With
familiar shell-style commands (e.g., cd, ls, doc, cat), users can navigate
through Python objects, inspect their attributes, and explore libraries and
APIs deeply.

Key functionalities:
- Interactive navigation of objects (cd, pwd, cdh, tree)
- Listing and filtering attributes (ls, find)
- Detailed inspection (doc, cat, type, signature)
- Mapping modes for attribute vs. collection contents
- Shell-like conveniences (pipes, aliases, history)
- Python evaluation and scripting capabilities
"""

import argparse
import ast
from contextlib import contextmanager, nullcontext, redirect_stdout, redirect_stderr
from datetime import datetime
import fnmatch
import functools
import glob
import inspect
import itertools
from io import StringIO
import os
from os.path import expanduser, exists
import pprint
# import pydoc
import re
import subprocess
import sys
import textwrap
import uuid
from tempfile import NamedTemporaryFile
from typing import Any, Callable, IO, List, Optional, Union

import cmd2
from cmd2 import Fg, ansi, utils
from cmd2.history import HistoryItem
from cmd2.utils import truncate_line

from . import dirops
from . import pob_unparse
from . import strpath
from . import infocmds
from .pobnode import PobNode, style_str
from .common import (
    MissingInfoOptions,
    PobPrefs,
    POBNODE_NAME,
    SELF_NAME,
    short,
    temporary_setting,
)
from .infocmds import (
    # CMD_CAT_INFO,
    CMD_CAT_LIST_DIR,
    CMD_CAT_MAP,
    CMD_CAT_PATH_MANIPULATION,
    CMD_CAT_POBSHELL_TESTING,
    CMD_CAT_PYTHON,
    CMD_CAT_SCRIPTING,
    CMD_CAT_UNCATEGORIZED,
    CMD_CAT_UTILS,
    HideArgumentHelpFormatter,
    INFOCMD_ARGS,
    INFOCMD_SPECS,
    argstr_LIMIT,
    argstr_TARGET,
    # argstr_all,
    argstr_enumerate,
    argstr_long,
    argstr_numlines,
    argstr_oneline,
    argstr_paged,
    argstr_pypath,
    argstr_quiet,
    # argstr_unstyled,
    argstr_verbose,
    argstr_xtralong,
    extract_filter_criteria,
    make_infomethod,
    make_match_func,
)

# Next is for reimport purposes, to support do_reset method
from . import common

POB_HALT = 1
POB_CONTINUE = 2


# ==============================================================================
# # string processing utility
# ==============================================================================
def parse_cmds(cmdstr):
    """split ';' delimited string of commands into list of command strings """
    # hacky parsing of an input string that possibly contains multiple pob commands
    # into separate strings each with one command and its args

    # TODO: Use proper parsing here, so we don't split on ';' if its inside a string
    # TODO: Use cmd2's command parser to check each cmd cmdstr and raise an error if required
    if ";" in cmdstr:
        return cmdstr.split(';')
    else:
        return [cmdstr]



# ==============================================================================
# # Text formatting utilities   ================================================
# ==============================================================================

def boldit(txt: str) -> str:
    """ Wrap text in string txt with ANSI escape codes to make it bold
    """
    return ansi.style(f"{txt}", bold=True)


class RunningTable:
    """
    Utility class for formatting and aligning output in human-readable columnar format.
    Used by Pobiverse.output_infos for 'ls -l'-style outputs and other commands invoked
    with the '-1' one-liner output option

    Details:
    - The first column has a user-specified maximum width, if any.
    - Middle columns use predefined widths configured in PobPrefs (a configuration class).
    - The last column is truncated, if necessary, to ensure the total output stays within max_width (if provided).

    Note: The class primarily handles up to three columns for styling and alignment.

    """

    def __init__(self, max_col0_width: Optional[int], styles: Optional[List[dict]]):
        """
        Initialize a `RunningTable` instance with column width and style configurations.

        Args:
        max_col0_width (Optional[int]):
            The maximum width for column 0. If the column's content exceeds this width, it will be truncated.
            Specify `None` to impose no width limit for this column.

        styles (Optional[List[dict]]):
            A list of up to 3 dictionaries representing ANSI styles for each column. Each dictionary defines
            the stylistic attributes (e.g., color, font style) for that column.
            If fewer than 3 styles are provided, the list is padded with empty dictionaries to apply no styles
            to unspecified columns.
            If `None` is provided, no styles will be applied.
        """
        self.max_col0_width = max_col0_width
        self.max_width = PobPrefs.width

        # We only need 3 columns in col_width_chars for typical usage:
        #   [width_for_col0, width_for_col1, width_for_col2, ...]
        #   but the first (col0) will be overridden by max_col0_width if set.
        #   The last column is "flex" so we might let it expand, or set a limit if desired.

        # Load config from PobPrefs (example: each "tab" is 8 chars).
        # If you have more columns in PobPrefs.columns, slice or handle them as needed.
        # self.col_width_chars = []
        # for k in sorted(PobPrefs.columns.keys()):
        #     self.col_width_chars.append(PobPrefs.columns[k] * 8)
        # # Make sure we have at least 3 columns worth of widths:
        # while len(self.col_width_chars) < 3:
        #     self.col_width_chars.append(16)  # some default fallback

        # If you need a global maximum row width, store it or reuse self.max_width
        # from constructor. For simplicity, we won't do that here; you can extend as needed.

        # How many spaces to use between columns
        self.col_sep = "  "
        # Optionally add zero-width separator (at final step of self.row to avoid truncate_line issues)
        self.col_sep_postscript = "\0"  if PobPrefs.null_separator else ""

        # Styles
        self.styles = styles if styles else []
        self.styles.extend([{}]*(3 - len(self.styles)))  # pad to at least 3 style dicts


    def row(self, cols: list) -> str:
        """
        Format one "row" of columns into a single aligned string.
        - Column 0: truncated to self.max_col0_width if set
        - Middle columns (if any): truncated/justified to col_width_chars[i].
        - Last column (if it exists): by default we do not forcibly truncate.


        Returns:
            A single string containing the row, with ANSI styling applied (if styles are defined).
        """
        out_cols = []
        total_width = 0

        for i, col_data in enumerate(cols):
            text = str(col_data)
            # Decide how wide this column should be
            if i == 0:
                configured_width = self.max_col0_width
            elif i < len(cols) - 1:
                # Use configured width for middle columns
                configured_width = PobPrefs.column_width
                if configured_width + total_width > self.max_width:
                    break  # we've exceeded max_width; don't add more columns
            else:
                # It's the last column, give it the remaining space
                configured_width = self.max_width - total_width

            # Truncate, pad or skip column according to configured width  ----

            if configured_width <= 0:
                continue   # Current column has been configured to zero width; continue to next field

            if len(text) > configured_width:
                # ansi aware truncation with ellipsis
                text = truncate_line(text, max_width=configured_width)

            # Left‐justify in that width for alignment
            if i < len(cols) - 1:
                text = self.ansi_ljust(text, configured_width)

            # calc width style aware  since text may be styled (e.g. cat command output)
            total_width += ansi.style_aware_wcswidth(text) + len(self.col_sep)

            # Apply column specific ANSI styling
            if i < len(self.styles):
                text = cmd2.ansi.style(text, **self.styles[i])

            out_cols.append(text)

        return (self.col_sep + self.col_sep_postscript).join(out_cols)



    ANSI_ESCAPE = re.compile(r'\x1b\[[0-9;]*m')

    @classmethod
    def ansi_ljust(cls, text, width, fillchar=' '):
        """ Left-justify text while correctly handling ANSI escape codes. """
        clean_text = cls.ANSI_ESCAPE.sub('', text)  # Strip ANSI codes for width calculation
        padding_needed = width - ansi.wcswidth(clean_text)  # Calculate width without ANSI codes
        return text + (fillchar * max(0, padding_needed))



# ==============================================================================
# # command processing class  =================================================
# ==============================================================================

class Pobiverse(cmd2.Cmd):
    """
    Pobiverse manages the object namespace, command parsers, and runtime behavior
    that enables users to navigate and inspect Python objects like a directory tree.
    It provides commands for:

    - Navigating Python objects as if they were directories
      (using commands such as cd, pwd, and tree).
    - Listing and filtering attributes (ls with various options).
    - Inspecting documentation, signatures, values, and source code
      for objects (doc, cat, type, mro).
    - Performing recursive searches within object hierarchies (find).
    - Switching between different mapping modes (e.g., attributes vs.
      contents for lists, dicts, etc.).
    - Executing Python code (py, eval, rooteval) within the shell's context.
    - Managing advanced shell-like features (aliases, history, macros).

    This class orchestrates the behind-the-scenes logic for these commands,
    maintains the current path into the object graph, and integrates each
    command's parser with the broader interactive environment.

    The behavior of Pobiverse can be configured during initialization via
    parameters such as the root object, and startup commands.
    See the `__init__` constructor for details


    Parameters
    ----------
    root : Any, optional
        The object or namespace to serve as the initial "root" context.
        If not provided, Pobiverse will attempt to infer a frame from its caller.
    map_init : Any, optional
        Defines the initial mapping configuration. This controls how attributes
        and contents are exposed as users navigate the object hierarchy.
    interactive : bool, optional
        Whether to run in interactive mode (using the cmd loop). Setting
        this to False allows the class to be used in scripted or programmatic
        contexts without interactive behavior.
    user_defs_path : str, optional
        Path to a python module for user to configure various settings & definitions
    cmds : str, optional
        A single Pobiverse command or multiple commands separated by semicolons.
    **kwargs
        Additional optional keyword arguments for configuring Pobiverse’s behavior,
        such as prompt customization or toggling specific flags. Advanced users
        can use these to fine-tune startup or execution.

    Typical usage involves creating or obtaining a Pobiverse instance
    and invoking its main loop or commands to explore live objects.
    """

    def __init__(self, root, interactive, map_init='', **kwargs):

        # paths for settings file, history and startup script
        prefs = self.setup_prefs(kwargs)


        # INITIALIZE command-processing state  -----------------
        self.contentkeys = {}
        # temporary store for contentkeys provided in command arguments
        #   we have to hide contents of these keys to prevent cmd2 from parsing inside them
        #   we do it by temporarily substituting content by a uuid key into this dict

        self.lsx_context = False  # tell Pobiverse commands that they're not being run as part of an 'ls -x' command
        self.mount_history = []   # track classes added to root namespaces by 'mount' command
        self.perror_to_poutput = False  # set to True while creating or testing transcript files
                                        #   so transcripts capture and test perror messages
                                        # and set to None when cd'ing to match's namespace to execute find's --cmd
                                        #   to eat error messages when a path can't be retrieved
        self.keyboard_interrupt = False  # flag that stops command loops on ^C

        # track paths in poutput for --enumerate; use with $-prefix, e.g. cd $1   ls -l $42
        self._result_paths = []


        # info COMMAND factory: Initialize do_* methods for info commands ---------------------------

        # N.B. PobPrefs.load_settings must be executed before this step; make_infomethod has a dependency on
        #   make_infomethod, which uses imethod, which uses make_exclude_func which uses INFOFILTERS,
        #       - which is updated by PP.load_settings
        self.make_methods_and_parsers()

        super().__init__(**prefs)

        self.doc_leader = ("""Use 'help -v' to list command descriptions\n""" 
                            """    'help <COMMAND>' for syntax""")
        self.doc_header = """    'man' for list of man pages with example usage"""

        # SETTINGS-RELATED INITIALIZATION ===========================================================================
        if PobPrefs.DEBUG and ('-t' in sys.argv or '--test' in sys.argv):
            # we're in DEBUG mode, and running a test
            self.allow_style = ansi.AllowStyle.TERMINAL
            # prevent test scripts from clobbering history
            self.persistent_history_file = ''
        else:
            self.allow_style = ansi.AllowStyle.ALWAYS

        # Set a separate help category for commands defined in cmd2
        self.default_category = CMD_CAT_UNCATEGORIZED

        if not PobPrefs.DEBUG:  # pragma: no cover
            self.disable_category(CMD_CAT_POBSHELL_TESTING, "Only available in DEBUG mode")
            self.hidden_commands.extend(['break', 'dir'])

        #  map related settings  ------------------------------

        # Preferences for mapping python objects -> directories
        #   all these settings have A value for 'DATA' preset, 'CODE' preset and 'EVERYTHING' preset
        #   when map_preset is changed with map command, they should pick up their alternate values

        self.add_settable(cmd2.Settable('global_ns', str,
                                        "Global namespace used when evaluating Python expressions\n"
                                        "  Used by 'eval', 'rooteval' and 'printpy' commands.\n"
                                        "  Also by '--matchpy' filter and find's '--printpy' option\n"
                                        "    ['none': Only builtins, '/': root namespace,\n"
                                        "     'user': user_defs.py namespace]",
                                        choices=["none", "/", "user"],
                                        settable_object=PobPrefs))

        self.add_settable(cmd2.Settable('contents_limit', int,
                                        "Limit the number of content items mapped as members of Collections and Sequences",
                                        settable_object=PobPrefs))

        self.add_settable(cmd2.Settable('simple_cat_and_doc', bool,
                                        """'cat' of property attributes combines fget/fset/fdel;\n"""
                                        """  'doc' suppresses empty docstrings and docs for instances\n"""
                                        """  of builtin data classes such as lists and ints""",
                                        settable_object=PobPrefs))

        self.add_settable(cmd2.Settable('auto_import', bool,
                                        "Automatically import subpackages and modules as members"
                                        "  (risk of code execution on import)\n",
                                        settable_object=PobPrefs))

        # Settings to hide some objects from find command -------

        self.add_settable(cmd2.Settable("default_maxdepth", int,
                                        "'find' command default maxdepth; how deep to search.\n"
                                        "  Set to '-1' for unlimited depth (beware recursive paths)",
                                        settable_object=PobPrefs))

        self.add_settable(cmd2.Settable("recursive_find_protection", int,
                                        "'find' command logic for pruning paths that appear recursive\n"
                                        "  ['0': don't prune recursive paths\n"
                                        "   '1': prune paths having duplicate ids\n"
                                        "   '2': prune paths with duplicate ids or name & type]",
                                        choices = (0,1,2),
                                        settable_object=PobPrefs))


        #   Output formatting related settings -------------------------

        self.prompt_char = '▶'
        # self.prompt_char = '▶︎'
        # self.prompt_char = '⌲'
        # self.prompt_char = '▷'
        # self.prompt_char = '➤'

        self.add_settable(cmd2.Settable('prompt_char', str, "Character used for Pobshell prompt ",
                                        settable_object=self))

        self.add_settable(cmd2.Settable('width', int, "Terminal width at which to truncate or wrap output",
                                        settable_object=PobPrefs))

        self.add_settable(cmd2.Settable('path_width', int, "Width of paths in output; longer paths get truncated",
                                        settable_object=PobPrefs))

        self.add_settable(cmd2.Settable('column_width', int, "'ls -l' listings, width of middle columns",
                                        settable_object=PobPrefs))

        self.add_settable(cmd2.Settable('null_separator', bool, r"'ls -l' listings use \0 separator",
                                        settable_object=PobPrefs))

        self.add_settable(cmd2.Settable('theme', str,
                                        f'Color scheme name [valid values: {", ".join(PobPrefs.themes.keys())}]',
                                        choices=PobPrefs.themes.keys(),
                                        settable_object=PobPrefs))

        self.add_settable(cmd2.Settable('linenumbers', bool, "'cat' source code listings include (original) linenumbers",
                                        settable_object=PobPrefs))

        self.add_settable(cmd2.Settable('flatten_multiline', bool, "Flatten multiline output to one (perhaps very wide) line",
                                        settable_object=PobPrefs))


        #   cruft suppression -----

        self.add_settable(cmd2.Settable('missing', str,
                                        "Preferred output for info that is N/A or missing\n" +
                                        MissingInfoOptions.valid_values,
                                        choices=MissingInfoOptions.choices,
                                        settable_object=PobPrefs))


        # FIND command's DEBUG AND TRACE SETTINGS  -------------------------

        self.find_flags = ''
        self.add_settable(cmd2.Settable('find_flags', str,
                                        "'find' command flags specifying debug/progress feedback\n"
                                        "  upper-case = excluded nodes, lower-case = included/walked\n"
                                        "  [t=test; y=yield; w=walk children; c=walk child;\n"
                                        "    f=finished node; W=don't walk; D=too deep; P=pruned;\n"
                                        "    V=previously visited no-match]",
                                        settable_object=self))

        # find's trace messages break test suite output matching; set default trace_frequency to 0 in DEBUG mode
        self.trace_frequency = 0 if PobPrefs.DEBUG else 500
        self.add_settable(cmd2.Settable('trace_frequency', int,
                                        "'find' command frequency of momentary update messages. \n"
                                        "  Object path is displayed for 1 in every N objects walked,\n"
                                        "  ['0': No messages, '1': Every object, '500': 1 in 500]",
                                        settable_object=self))

        # Debug and test settings   -------------------------

        self.test_collector = None      # if None, §-comments won't collect cmds

        # SET UP ROOT NAMESPACE ======================================================================================

        # store pob object ids in PobPrefs.introspection_ids, so they can be excluded from root
        pob_modules = [v for k, v in sys.modules.items() if k.startswith("pobshell")]
        #   {'pobshell': sys.modules['pobshell'], 'pobmain': sys.modules['pobshell.pobmain']}
        PobPrefs.introspection_ids = {id(ob) for ob in [self] + pob_modules}
        self.root = root  # The Python object providing "root directory" of pobshell "filesystem"
        self.rootns = dirops.PobNS(self.root, abspath='/')  # Persistent Pob namespace for root object
        self.rootpn = PobNode('/', obj=self.rootns)  # root PobNode; 'obj' attribute references root namespace

        # SET UP CURRENT PATH OBJECT ==================================================================================
        self.curr_path = self.rootpn
        self.curr_path_history = []


        # HOOKS AND OTHER TRICKERY ===================================================================================

        super().register_precmd_hook(self.replace_contentkeys)

        # monkey patch writing-to-history so contentkeys aren't written as hex uuids
        self.orig_history_append = self.history.append
        self.history.append = self.history_append

        # monkey patch ansi aware write to write html if required
        cmd2.ansi.style_aware_write = ansi_aware_write_jupyter

        # initialization_complete is used by self.py_locals property so it can ignore eval by cmd2's init
        self.initialization_complete = True


        # SET UP DEFAULT FILTERSETS AND PRUNESETS  ===================================================================

        # -- Store filters from 'hide' command
        #   By default commands will filter out private members, i.e. names with '_' prefix
        self._nolist_funcs = {}
        self._nolist_criteria = {}
        # construct an argparse namespace for extract_filter_criteria, which expects 'args' from a cmd2 command
        nolist_args = argparse.Namespace(name='_*')
        filters_dict = extract_filter_criteria(nolist_args, infocmds.INFOFILTERS, for_show=False)  # {infofilter_name: (pattern, matchfunc)}
        self.persist_filterdict(filters_dict, quiet=True)
        self._nolist_func = lambda pn: any(mf(pn) for mf in self._nolist_funcs.values())


        # RUN ANY STARTUP COMMANDS ==================================================================================

        if map_init:
            self.onecmd_plus_hooks(f'map -q {map_init}')

        if self.startup_scripts:
            for script_path in self.startup_scripts:
                if script_path and exists(script_path):
                    self.onecmd_plus_hooks(f'run_script {script_path}', add_to_history=False)

        if self.startup_cmds:
            cmd_list = parse_cmds(self.startup_cmds)
            for cmd in cmd_list:
                if self.onecmd_plus_hooks(cmd):
                    break

        # DISPLAY WELCOME BANNER  -------------------------
        if interactive:
            self.output_pobshell_banner()


    def setup_prefs(self, kwargs):
        """ Handle preferences passed in kwargs & prep preferences for cmd2 init """

        prefs = {}

        # Handle DEBUG setting
        PobPrefs.init_options({'DEBUG': kwargs.pop('DEBUG', False)})

        # handle default shortcuts & any that are user specified
        # Default shortcuts
        shortcuts = {'?': 'find', '!': 'shell', ':': 'eval', '::': 'rooteval', '##': 'comment',
                     '%': 'printpy', '§': 'addtest'}
        shortcuts.update(kwargs.pop('shortcuts', {}))  # if user provided shortcuts use them too
        prefs['shortcuts'] = shortcuts

        # cli processing
        # Tell Cmd2 not to process argv unless DEBUG mode and we're running tests
        #   (in which case cli args are needed for running transcripts)
        prefs['allow_cli_args'] = PobPrefs.DEBUG and any(arg in sys.argv for arg in ('-t', '--test', 'killsession')),

        # shell settings
        prefs['include_py'] = True
        # Allow ipython shell only if not already running from an ipython shell
        try:
            in_ipython = get_ipython()
        except NameError:
            in_ipython = False
        prefs['include_ipy'] = not in_ipython

        # multiline commands
        # comment & addtest are the only multiline commands, abbreviated '##' and '§' respectively
        #      terminate multiline comments and addtest descriptions with a semicolon
        prefs['multiline_commands'] = ['addtest', 'comment'],

        # paths for history, user_defs.py and startup scripts ---------

        config_dir = expanduser("~/.pobshell")

        # persistent history
        # Grab any user-specified path (or a sentinel if none provided)
        history_path = kwargs.pop('persistent_history_file', 'NOT_PROVIDED')
        if history_path == 'NOT_PROVIDED':
            # user did not specify; use default path
            history_path = os.path.join(config_dir, "history")
        elif history_path is None or history_path == '':
            # user explicitly wants no persistent file; leave as None or ""
            pass
        # otherwise, user gave a valid path, so leave it
        prefs['persistent_history_file'] = history_path

        # If in debug mode, override history length default
        if PobPrefs.DEBUG:
            prefs['persistent_history_length'] = 50000

        # Set up path for user_defs.py to read user settings and additional INFOFILTERS
        user_defs_path = kwargs.pop('user_defs_path', None)
        if not user_defs_path:
            user_defs_path = os.path.join(config_dir, "user_defs.py")
            if not exists(user_defs_path):
                user_defs_path = None
        PobPrefs.load_settings(user_defs_path)
        infocmds.update_INFOFILTERS()

        # startup scripts
        self.startup_scripts = [kwargs.pop('startup_script', None), os.path.join(config_dir, "pobshellrc")]
        self.startup_cmds = kwargs.pop('cmds', None)

        # pass any remaining kwargs to cmd2 directly
        prefs.update(kwargs)
        return prefs

    # ==============================================================================
    # ## Hooks and monkey patch methods =====================================
    # ==============================================================================


    # Create methods
    def make_methods_and_parsers(self):
        """
        Create info methods and add arguments to parsers of existing methods do_find, do_tree, do_hide and do_show

        NB uses the doc command as a flag to check if we have previously created do_[command] attributes on Pobiverse
        In which case we bail and create none. Can happen if pob.py tries to reset / reinitializse Pobiverse
        """

        if hasattr(self, 'do_doc'):
            return

        # This loop creates the Inspection commands specced in infocmds.py and sets them as attributes of the Pobiverse class
        for info_name in INFOCMD_SPECS.keys():
            setattr(Pobiverse, f'do_{info_name}', make_infomethod(info_name, Pobiverse))

        # Find's filter arguments picked up from user_defs.py via PobPrefs ---------
        flag_desc = ',  '.join(arg_names[0] for arg_names, _ in INFOCMD_ARGS
                               if arg_names[0].startswith('--is'))

        find_flagfilter_group = self.find_parser.add_argument_group(
            title="Flag criteria",
            description=(
                    "Find objects that satisfy is* functions. These criteria don't take a pattern \n"
                    + textwrap.fill(flag_desc, width=80))
        )

        # flag_filter_group.add_argument(*args, **kwargs)
        for arg_names, arg_specs in INFOCMD_ARGS:
            if not (arg_names[0].startswith('--is') or arg_names[0].startswith('--nis')):
                continue
            find_flagfilter_group.add_argument(*arg_names, **arg_specs)

        find_pattern_criteria_group = self.find_parser.add_argument_group(
            title='Pattern-matching criteria',
            description=(
                """Find objects whose characteristics match a glob or regex PATTERN\n"""
                """Each PATTERN selects objects whose Pobshell command result is a match\n"""
                """--abc abstract base class interfaces, --abspath: pobshell path,\n"""
                """--cat: obj source code, --doc: obj doc string,\n"""
                """--repr: repr(obj), --str: str(obj), --filepath:  source file path,\n"""
                """--id: id(obj), --mro: mro tuple, --name: object's name,\n"""
                """--predicates: names of inspect.is* functions that return True,\n"""
                """--pydoc: pydoc content, --signature: signature of callable,\n"""
                """--type: type(obj), --typename: type(obj).__name__,\n"""
                """--which: defining class of method\n"""
            ))

        # find's pattern match filters ------
        # This loop adds additional filter args for do_find, now that PobPrefs.load_settings has picked up
        #   additional definitions from user_defs.py
        # We exclude last 2 (matchpy and noraise, they're done in do_find argparser init, just above do_find's def
        for args, kwargs in INFOCMD_ARGS[:-2]:
            if args[0].startswith('--is') or args[0].startswith('--nis'):
                continue
            find_pattern_criteria_group.add_argument(*args, **kwargs)

        # find's Python expression match ------
        find_pattern_criteria_group.add_argument('--matchpy', type=str, metavar='PYEXPR',
                                                 help='match obj if python expression PYEXPR returns True')

        # Add filter arguments for do_hide & do_tree ---------
        for args, kwargs in INFOCMD_ARGS:
            self.hide_parser.add_argument(*args, **kwargs)
            self.tree_parser.add_argument(*args, **kwargs)
        self.hide_parser.add_argument('-q', '--quiet', action='store_true', help="don't echo filter change to output")

        # Add filter arguments for do_show ---------
        for args, _ in INFOCMD_ARGS:
            kwargs = {'action': 'store_true', 'help': f'remove filter for {args[0][2:]}'}
            self.show_parser.add_argument(*args, **kwargs)
        self.show_parser.add_argument('-q', '--quiet', action='store_true', help="don't echo filter change to output")

        # Give PV's do_find & do_tree methods extra arguments for the prunesets defined in user_defs.py
        for k, v in PobPrefs.prunesets.items():
            self.pruneset_option.add_argument('--' + k, action='store_true', help=inspect.getdoc(v))
                                              # help=f'focus search on {k} objects by pruning irrelevant paths ')
            # Focus on code objects (prune non-code)
            self.tree_parser.add_argument('--' + k, action='store_true',
                                          help=inspect.getdoc(v))
                                          # help=f'focus search on {k} objects by pruning irrelevant paths ')


    def onecmd_plus_hooks(
            self,
            line: str,
            *,
            add_to_history: bool = True,
            raise_keyboard_interrupt: bool = False,
            py_bridge_call: bool = False,
            orig_rl_history_length: Optional[int] = None,
    ) -> bool:
        """override cmd2 method to support 'echo' option outside scripts"""
        if self.echo:
            self.poutput(f"# {line}")
        return super().onecmd_plus_hooks(
            line,
            add_to_history=add_to_history,
            raise_keyboard_interrupt=raise_keyboard_interrupt,
            py_bridge_call=py_bridge_call,
            orig_rl_history_length=orig_rl_history_length,
        )


    def runcmds_plus_hooks(
            self,
            cmds: Union[List[HistoryItem], List[str]],
            *,
            add_to_history: bool = True,
            stop_on_keyboard_interrupt: bool = False,
    ) -> bool:
        """
        Override cmd2.runcmds_plus_hooks to abort the cmd loop as soon as the user presses Ctrl‑C.
        """
        # reset flag for this command list
        self.keyboard_interrupt = False

        for line in cmds:
            if isinstance(line, HistoryItem):
                line = line.raw

            try:
                # Let cmd2 execute the command
                if self.onecmd_plus_hooks(
                        line,
                        add_to_history=add_to_history,
                        raise_keyboard_interrupt=stop_on_keyboard_interrupt,
                ):
                    return True

            except KeyboardInterrupt:
                # onecmd_plus_hooks re‑raised; cmd2 cleanup is done
                if stop_on_keyboard_interrupt:
                    return True                # bubble “stop” upward

            # Did sigint_handler set the flag during this command?
            if stop_on_keyboard_interrupt and self.keyboard_interrupt:
                self.keyboard_interrupt = False  # reset before returning
                return True

        return False


    # methods to support interrupt of commands that recurse to call other commands  -----------------------
    #   commands that recurse need to reset state if interrupted


    def items(self):
        # List Pobiverse contents
        # Doing it this way helps prevent recursion crash in debug mode when exoloring Pobiverse instance
        return [(k, getattr(self, k)) for k in dir(self) if k != 'py_locals']



    def sigint_handler(self, *args, **kwargs) -> None:
        """ Set flag for ^C and tidy any trace or debug messages from PobNode.ns_walk"""

        self.keyboard_interrupt = True

        with self.sigint_protection:

            if self.trace_frequency > 0:
                # Print blank line in case find's most recent update message is visible
                #   or we may overprint a long find update message with a short signint message
                print(" " * (PobPrefs.width - 1), end="\r")

        print()  # Write a linefeed, we likely have ^C on current line

        super().sigint_handler(*args, **kwargs)


    # Pre-parse input lines  -------------------------------------------

    def replace_contentkeys(self, data: cmd2.plugin.PrecommandData) -> cmd2.plugin.PrecommandData:
        # ======== HOOK ==========
        # supercedes _input_line_to_statement
        # the statement object created from the user input
        # is available as data.statement
        # ------------

        line = data.statement.raw
        if PobPrefs.contentkey_delimiter not in line:
            return data

        btsplit = line.split(PobPrefs.contentkey_delimiter)
        for i, ele in enumerate(btsplit):
            # odd numbered elements were contentkey_delimiter-escaped
            if i % 2 == 1:
                bt_uuid = uuid.uuid4()
                self.contentkeys[bt_uuid.hex] = ele  # save the contentkey expr in dict for later retrieval
                btsplit[i] = bt_uuid.hex

        updated_line = PobPrefs.contentkey_delimiter.join(btsplit)
        data.statement = self.statement_parser.parse(updated_line)

        return data



    # replace original contentkey_delimiter expressions in the arg namespace we receive from cmd2's argparse command line processing
    def recover_contentkey_args(self, args):
        #  for each arg if it contains contentkeys, subst the original contentkey expression
        #    mutates args Namespace object
        for a in dir(args):
            if a.startswith('_') or a.startswith('cmd2'):
                continue

            s = getattr(args, a)
            if type(s) is not str or PobPrefs.contentkey_delimiter not in s:
                continue

            fixed_s, hexes = self.recover_contentkeyed_str(s)
            for h in hexes:
                del self.contentkeys[h]   # Ok to delete them now
            setattr(args, a, fixed_s)


    # helper method for contentkey_delimiter replacement
    def recover_contentkeyed_str(self, s):
        #  recover the content key expression in string s, by looking up the uuid it contains in the dict self.contentkeys
        #   return the hexes too, so the dict entry can be deleted later
        hexes = []
        btsplit = s.split(PobPrefs.contentkey_delimiter)
        for i, ele in enumerate(btsplit):
            # odd numbered elements were contentkey_delimiter-escaped
            if i % 2 == 1:
                uuid_hex = ele
                hexes.append(uuid_hex)
                btsplit[i] = self.contentkeys[uuid_hex]
                # TODO: Check if the uuid hexes are all cleaned up from self.contentkeys
        return PobPrefs.contentkey_delimiter.join(btsplit), hexes


    #   This method monkey patches history processing of parent class, to fix history entries containing contentkeys
    def history_append(self, s):
        """Append a new statement to the end of the History list, expanding any contentkeys
            :param s: Statement object which will be composed into a HistoryItem
                        and added to the end of the list
        """
        if PobPrefs.contentkey_delimiter not in s:
            history_item = HistoryItem(s) if isinstance(s, cmd2.Statement) else s
        else:
            history_item = HistoryItem(cmd2.Statement('', raw=s.command+' '+self.recover_contentkeyed_str(s)[0]))

        self.orig_history_append(history_item)


    def default(self, statement: cmd2.Statement) -> Optional[bool]:  # type: ignore[override]
        """Overrides cmd2 default method, to replace any contentkey uuids in the error message

        Executed when the command given isn't a recognized command implemented by a do_* method.
        :param statement: Statement object with parsed input
        """

        err_msg, hexes = self.recover_contentkeyed_str(self.default_error.format(statement.command))
        for h in hexes:
            del self.contentkeys[h]

        # Set apply_style to False so default_error's style is not overridden
        self.perror(err_msg, apply_style=False)
        return None


    def perror(self, *args, **kwargs) -> None:
        """Override cmd2 perror to send error messages to stdout when testing"""
        if self.perror_to_poutput is True:  # So transcript tests can also test error messages
            kwargs.pop('apply_style', None)  # remove this kwarg because poutput doesn't have it
            return self.poutput(*args, **kwargs)
        elif self.perror_to_poutput is False:  # pragma: no cover
            super().perror(*args, **kwargs)


    def pexcept(self, msg: Any, *, end: str = '\n', apply_style: bool = True) -> None:
        """Print Exception message to sys.stderr. If debug is true, print exception traceback if one exists.

        Overridden cmd2 pexcept just to change color of warning message in light theme
        """
        if self.debug and sys.exc_info() != (None, None, None):
            import traceback
            try:
                traceback.print_exc()
            except:
                # Trap crash due to exception reporting e.g.
                #   if debug setting is true, this crashes to OS prompt:
                #     /sklearn/os/supports_dir_fd ▶ :readlink
                print("!! Exception raised while printing exception message")

        if isinstance(msg, Exception):
            final_msg = f"EXCEPTION of type '{type(msg).__name__}' occurred with message: {msg}"
        else:
            final_msg = str(msg)

        if apply_style:
            final_msg = ansi.style_error(final_msg)


        if not self.debug and 'debug' in self.settables:
            warning = "\nTo enable full traceback, run the following command: 'set debug true'"
            style_warning = functools.partial(ansi.style, fg=Fg[PobPrefs.current_theme['warning']])
            final_msg += style_warning(warning)

        self.perror(final_msg, end=end, apply_style=False)


    @contextmanager
    def stacked_command(self, cmd: str):
        """Guaranteed to run pob command "cmd" when context manager exits"""
        try:
            yield
        finally:
            with self.sigint_protection:
                self.onecmd_plus_hooks(cmd, add_to_history=False, raise_keyboard_interrupt=False)



    # ==============================================================================
    # ## path ops ==================================================================
    # ==============================================================================


    # tab completion ----------------------------------------------------------------

    # https://github.com/python-cmd2/cmd2/blob/master/examples/python_scripting.py#L34-L48
    # https://github.com/python-cmd2/cmd2/blob/8e9a21c02bc317ba927d758075c8562d0c0b2474/cmd2/cmd2.py#L1483

    def ns_path_complete(
            self, text: str, line: str, begidx: int, endidx: int, *,
            path_filter: Optional[Callable[[str], bool]] = None) -> List[str]:   # pragma: no cover
        """Performs completion of dir paths
        :param text: the string prefix we are attempting to match (all matches must begin with it)
        :param line: the current input line with leading whitespace removed
        :param begidx: the beginning index of the prefix text
        :param endidx: the ending index of the prefix text
        :param path_filter: optional filter function that determines if a path belongs in the results
                            this function takes a path as its argument and returns True if the path should
                            be kept in the results
        :return: a list of possible tab completions
        """
        # TODO This breaks cmd2 rules, it should not be a bound method, but I need a handle to PV instance
        #   for access to curr_path

        # Used to replace cwd in the final results
        cwd = self.curr_path.abspath
        cwd_added = False

        # If the search text is blank, then search in the CWD for *
        if not text:
            search_str = strpath.join(self.curr_path.abspath, '*')
            cwd_added = True
        else:
            # Purposely don't match any path containing wildcards
            wildcards = ['*', '?']
            for wildcard in wildcards:
                if wildcard in text:
                    return []

            # Start the search string
            search_str = text + '*'

            # If the search text does not specify directory, then use current working directory
            if not strpath.dirname(text):
                search_str = strpath.join(self.curr_path.abspath, search_str)
                cwd_added = True

        # Find all matching path completions
        try:
            matches = [p.abspath for p in self.pobnodes_for_target(search_str)]
        except dirops.PobMissingMemberException:
            return []

        # Filter out results that don't belong
        if path_filter is not None:
            matches = [c for c in matches if path_filter(c)]

        # Don't append a space or closing quote to directory
        if len(matches) == 1:
            self.allow_appended_space = False
            self.allow_closing_quote = False
            if cwd_added:
                found_name = matches[0][len(cwd):]
            else:
                found_name = matches[0]
            if found_name == text and text != '/':
                self.allow_appended_space = False
                self.allow_closing_quote = False
                matches[0] += '/'

        # Sort the matches before any trailing slashes are added
        matches.sort(key=self.default_sort_key)

        # Remove cwd if it was added to match the text readline expects
        if cwd_added:
            if cwd == '/':
                to_replace = cwd
            else:
                to_replace = cwd + '/'
            matches = [cur_path.replace(to_replace, '', 1) for cur_path in matches]

        if hasattr(self, 'match_history'):
            self.match_history.append(matches)
        else:
            self.match_history = [matches]
        return matches


    def mounted_names(self):  # pragma: no cover   (output of state change commands isn't supported by TestCollector)
        # provide list of names that have been mounted; choices provider to unmount command
        return self.mount_history


    # path utilities  ----------------------------------------------------------------

    def normpath(self, path: str) -> str:
        # curr_path aware conversion of path to absolute path
        # where path is a valid pobkey, or a relative or absolute path of pobkeys
        # supports absolute Python paths from root object if prefixed with '::'
        # NB normed paths have no trailing / except for root
        if path.startswith('::'):
            if self.rootns.holds_simple_frame:
                val = pob_unparse.Unparser(ast.parse(path[2:]))
            else:
                # insert "ROOT" as a name because ast.parse expects a container object name for
                # retrieval with "[ ]"  and an object name for attribute retrieval with "."
                # and remove the 4 chars of "ROOT" afterwards [4:]
                val = pob_unparse.Unparser(ast.parse("ROOT" + path[2:]))[4:]
            return '/' + str(val).strip()
        elif path.startswith(':'):
            val = pob_unparse.Unparser(ast.parse(path[1:]))
            path = str(val).strip()
        elif path.startswith('$'):
            path = self.result_path(path)  # retrieve path from enumeration results of prior command
        return strpath.abspath(path, self.curr_path.abspath)


    def result_path(self, dollar_path) -> str:
        # return path num $N from history
        #   Support $N and $N/subpath; $$ raises an exception (because cd $$ is an error)

        # extract path index (int) between $ char and '/' char or end of str
        subpath_pos = dollar_path.find('/')
        if subpath_pos == -1:
            index_str = dollar_path[1:]  # retrieve path from previously numbered results
        else:
            index_str = dollar_path[1:subpath_pos]
            subpath_str = dollar_path[subpath_pos:]

        try:
            index = int(index_str)
        except ValueError:
            raise dirops.PobMissingMemberException(f"TARGET of '{dollar_path}' is not supported for this command")

        try:
            path = self._result_paths[index]
            if not path:
                raise dirops.PobMissingMemberException(f"Invalid path ${index}: {path}")
            if subpath_pos == -1:
                return path
            else:
                return path + subpath_str
        except (IndexError, ValueError):
            raise dirops.PobMissingMemberException(f"No path number {index} exists in enumeration set")




    def safe_cd(self, abspath: str) -> bool:
        # try to cd to abspath, returning True for success and False for failure
        try:
            self.curr_path = PobNode(abspath, self.rootpn)
        except dirops.PobMissingMemberException:
            return False
        return True


    # ==========================================================================================
    # ## methods that run COMMANDs  ============================================================================
    # ==========================================================================================


    def cmd(self, cmdstr: str) -> None:
        """Run one or more ';'-delimited pob commands in cmdstr sending output via poutput and perror
        """
        self._cmd(cmdstr, capture_output=False)


    def _cmd(self, cmdstr: str, capture_output: bool) -> Optional[str]:
        """Executing command string containing one or more ;-delimited commands - perhaps capture output and return
         as a tuple of (out, err) strings"""

        def normalize(block: str) -> list[str]:
            """Normalize a block of text
            Split block of text into separate lines and strip trailing whitespace from each line.
            """
            if not block:
                return []
            return [line.rstrip() for line in block.splitlines()]

        if cmdstr:      # TODO: Use proper parsing here, so we don't split on ';' inside a string
            cmds = parse_cmds(cmdstr)

            outs, errs = [], []

            for cmd in cmds:
                if capture_output:
                    new_outs, new_errs = self._run_cmd(cmd.strip())
                    outs.extend(normalize(new_outs))
                    errs.extend(normalize(new_errs))
                else:
                    self.onecmd_plus_hooks(f'''{cmd.strip()}''', add_to_history=False, raise_keyboard_interrupt=True)

            if capture_output:
                return '\n'.join(outs), '\n'.join(errs)


    def _run_cmd(self, cmd: str) -> tuple[str, str]:
        """Clear out and err StdSim buffers, run the command, and return out and err"""

        saved_sysout = sys.stdout
        sys.stdout = self.stdout

        # This will be used to capture self.stdout and sys.stdout
        copy_cmd_stdout = cmd2.utils.StdSim(self.stdout)

        # This will be used to capture sys.stderr
        copy_stderr = cmd2.utils.StdSim(sys.stderr)

        try:
            self.stdout = copy_cmd_stdout
            with cmd2.cmd2.redirect_stdout(copy_cmd_stdout):
                with common.redirect_stderr(copy_stderr):
                    self.onecmd_plus_hooks(cmd,add_to_history=False, raise_keyboard_interrupt=True)
        finally:
            self.stdout = copy_cmd_stdout.inner_stream
            sys.stdout = saved_sysout

        out = copy_cmd_stdout.getvalue()
        err = copy_stderr.getvalue()
        return out, err



    # ==========================================================================================
    # ## cwd COMMANDs  ============================================================================
    # ==========================================================================================

    # commands related to current path

    # cd COMMAND  ---------------------------------------------------------------------

    cd_parser = argparse.ArgumentParser()
    cd_parser.add_argument('path', metavar="PATH", completer=ns_path_complete, help="name or path", suppress_tab_hint=True)
    cd_parser.add_argument('--noclobber', action="store_true", help=argparse.SUPPRESS)  # Don't clobber cdh history
    @cmd2.with_argparser(cd_parser)
    def do_cd(self, args):
        """Navigate to object path"""
        self.recover_contentkey_args(args)
        try:
            new_path = self.normpath(args.path)
            old_path = self.curr_path.abspath
            self.curr_path = PobNode(new_path, self.rootpn)
        except dirops.PobMissingMemberException:
            self.perror(f'cd: {args.path}: No such path')
            return

        if not args.noclobber:
            if not self.curr_path_history or self.curr_path_history[-1] != old_path:
                self.curr_path_history.append(old_path)


    def change_curr_path(self, new_pn) -> None:
        """'cd' to a path without adding to history, used by 'find' with '--cmd' """
        self.curr_path = new_pn


    mount_parser = argparse.ArgumentParser()
    mount_parser.add_argument('path', nargs='?', completer=ns_path_complete,
                              help='PATH of object whose class to mount',
                              suppress_tab_hint=True)
    mount_parser.add_argument('--alias', nargs='?', type=str, metavar="ALIAS",
                              help='name to use for mounted object')
    @cmd2.with_argparser(mount_parser)
    def do_mount(self, args):
        """Add object's class to root; and make it the current object path"""
        if args.path is None:
            self.poutput(pprint.pformat(self.mount_history))
            return

        # get a reference to the object at the path we were given
        try:
            objpath = self.normpath(args.path)
            objnode = PobNode(objpath, self.rootpn)  # objnode.obj is the python object at the path given
        except dirops.PobMissingMemberException:
            self.perror(f'mount: {args.path}: No such path')
            return

        if inspect.isclass(objnode.obj):
            # for a class mount the first entry in its mro
            mros = objnode.obj.mro()
            if len(mros) > 1:
                objtype = mros[1]  # mros[0] is current class, we want to mount the next
            else:
                objtype = mros[0]
        else:
            # or for an instance mount the class
            objtype = type(objnode.obj)

        # if module isn't current file, but module is in rootns, then cd to the path of the class within module
        if objtype.__module__ != "__main__":
            if objtype.__module__ in self.rootns:
                self.pfeedback("cd to existing directory.")
                self.onecmd_plus_hooks(f'''cd ::{objtype.__module__}.{objtype.__qualname__}''', add_to_history=False,
                                       raise_keyboard_interrupt=True)
                return

        # add class to rootns
        name = objtype.__name__ if args.alias is None else args.alias

        if name in self.rootns:
            if id(objtype) != id(self.rootns[name]):
                self.perror(f"Error: Name '/{name}' is already taken, for a different object")
                self.pfeedback(f"\t To mount it with a different name: 'mount {objpath} --alias NAME' ")
                return
            else:
                self.pfeedback("cd to existing directory")
        else:
            self.rootns[name] = objtype
            self.mount_history.append(name)
        self.onecmd_plus_hooks(f'''cd /{name}''', add_to_history=False, raise_keyboard_interrupt=True)


    unmount_parser = argparse.ArgumentParser()
    unmount_parser.add_argument('name',  metavar='NAME', nargs=argparse.OPTIONAL, choices_provider=mounted_names,
                                help='name of class to unmount from "/"-namespace',
                                suppress_tab_hint=True)
    @cmd2.with_argparser(unmount_parser)
    def do_unmount(self, args):
        """Remove path of class mounted as NAME, or most recently mounted class"""

        # get a name from args if one was provided
        name = args.name

        # get name of class to unmount
        if name is None:
            # No name was provided, get the most recent from mount_history
            try:
                name = self.mount_history.pop(-1)
            except IndexError:
                self.perror(f'unmount: No classes are mounted')
                return
        else:
            # A name was provided check it was previously mounted
            if name not in self.mount_history:
                self.perror(f'unmount: {name}: Was never mounted')
                return

        self.mount_history = [n for n in self.mount_history if n != name]

        # get path of name
        objpath = self.normpath(strpath.join("/", name))
        if name not in self.rootns:
            self.perror(f'unmount: {name}: Not found in namespace at "/" ')
            return
        del self.rootns[name]

        self.pfeedback(f"Mounted class was removed: {objpath} ")

        # if current path is /name, try to return to previous current path
        if self.curr_path.abspath == f"/{name}":
            for prevpath in self.curr_path_history[::-1]:
                if self.safe_cd(prevpath):  # change to the most recent path that still exists
                    return


    cdh_parser = argparse.ArgumentParser()
    cdh_parser.add_argument('index', nargs='?', type=int, help='index of path in history')
    cdh_parser.add_argument('-t', '--tail', action='store_true', help='list history tail')
    @cmd2.with_argparser(cdh_parser)
    def do_cdh(self, args):
        """
        Revisit an object path from the history of visited objects

        Behavior:
            - Without an index, lists the history of paths (or the tail if `--tail` is used).
            - With an index, changes to the path at the specified position in the history.
            - Displays an error if the index is invalid.

        Examples:
            cdh 2      # Navigate to the path at index 2 in history.
            cdh -t     # Show the most recent paths in history.
            cdh        # List the full history of paths.
        """
        if args.index is None:
            if args.tail:
                for i, p in enumerate(self.curr_path_history):
                    self.poutput(f"{i-len(self.curr_path_history)}: {p}")
            else:
                for i, p in enumerate(self.curr_path_history):
                    self.poutput(f"{i}: {p}")
            return

        try:
            new_path = self.curr_path_history[args.index]
            # print(f"{new_path=}")
        except IndexError:
            self.perror(f'No such history entry: {args.index}')
            return

        self.onecmd_plus_hooks(f'''cd {new_path}''', add_to_history=False, raise_keyboard_interrupt=True)


    @property
    def prompt(self):
        """
        Return the command prompt string, styled if allowed.
        """
        if self.allow_style != cmd2.ansi.allow_style.NEVER:  # pragma: no cover
            return cmd2.ansi.style(short(self.curr_path.abspath) + ' ' + self.prompt_char + ' ',
                                   fg=Fg[PobPrefs.current_theme['prompt']])
        else:
            return self.curr_path.abspath + ' ' + self.prompt_char + ' '


    @property
    def py_locals(self):  # pragma: no cover
        # set up namespace for python shell, invoked by do_py or do_ipy
        #   which copy py_locals result to use as namespace, and discard it afterwards,
        #   so namespace changes aren't persisted, even for root

        # If current path is (Pobiverse? PV instance?) don't copy py_locals into namespace dict returned by py_locals
        #   otherwise lots of recursion crashes
        if not self.initialization_complete:
            return

        if type(self.curr_path.obj) is type(self) and self.curr_path.obj == self:  # avoid introspection recursion
            eval_ns = {k: v for k, v in
                       dirops.get_pk_members(self.curr_path.obj, obj_is_Pobiverse=True)
                       if type(k) is str and k.isidentifier() and k != 'py_locals'}
        else:
            # cmd2.do_ipy does something nasty to the namespace we provide
            # and cmd2.do_py inserts {app, quit, exit, Completer, readline} , so only give a copy of the dict
            eval_ns = dirops.PobNS(self.curr_path.obj, abspath=self.curr_path.abspath, lazy=False).dict_copy()

            # the downside is rootns doesn't get persistent changes from ipy or py shells

            if not isinstance(self.curr_path.obj, dirops.PobNS):
                # if user wants PV.rootns to be a global namespace available at every path, and curr_path isn't '/'
                #   then update shell namespace with contents of that global namespace
                if PobPrefs.global_ns is not None and PobPrefs.global_ns != self.curr_path.abspath:
                    globals_pn = PobNode(PobPrefs.global_ns, self.rootpn)
                    global_ns = dirops.PobNS(globals_pn.obj, lazy=False).as_dict()
                    eval_ns.update(global_ns)  # if namespaces other than root are persistent in future, this may not be desirable

                if SELF_NAME not in eval_ns:
                    eval_ns[SELF_NAME] = self.curr_path.obj  # arbitrary python object at curr_path

                if POBNODE_NAME not in eval_ns:
                    eval_ns[POBNODE_NAME] = self.curr_path  # pass pobnode object representing curr_path

        return eval_ns



    @py_locals.setter
    def py_locals(self, newval):
        # cmd2's parent class assigns an empty dict value to py_locals, this eats the assignment.
        pass


    # pwd COMMAND  ---------------------------------------------------------------------

    def do_pwd(self, args):
        """Show current object path"""
        self.poutput(self.curr_path.abspath)



    # ======================================================================================
    # ## mapping COMMANDs and helper methods ===============================================
    # ======================================================================================
    #   - commands which change the mapping between python objects and namespace entries

    # persistent filtering: show & hide commands  ---------------------------------------------------------------------

    # helper function for do_hide
    def persist_filterdict(self, filters_dict, quiet=False):
        for key, value in filters_dict.items():
            if not quiet:
                self.poutput(f"Adding filterset entry: '{key}': '{value[0]}'")
            self._nolist_criteria[key] = value[0]
            self._nolist_funcs[key] = value[1]


    # Create the hide_parser
    hide_parser = argparse.ArgumentParser(formatter_class=HideArgumentHelpFormatter)

    @cmd2.with_argparser(hide_parser)
    def do_hide(self, args):
        """
        Persistently hide members by filtering on characteristics
        """
        # Update self._nolist_criteria from command line args

        filters_dict = extract_filter_criteria(args, infocmds.INFOFILTERS, for_show=False)  # {infofilter_name: (pattern, matchfunc)}
        self.persist_filterdict(filters_dict, quiet=args.quiet)

        # Build filter function; return True for PN's that match any 'hide' criterion
        self._nolist_func = lambda pn: any(mf(pn) for mf in self._nolist_funcs.values())
        if not args.quiet:
            self.poutput('Current filters:  '+str(self._nolist_criteria))


    # Create the show_parser
    show_parser = argparse.ArgumentParser(formatter_class=HideArgumentHelpFormatter)

    @cmd2.with_argparser(show_parser)
    def do_show(self, args):
        """
        Remove persistent filters set with the "hide" command
        """
        # Update self._nolist_criteria from command line args

        # for_show flag says we want a dict of {key: None}, no patterns or funcs expected
        filters_dict = extract_filter_criteria(args, infocmds.INFOFILTERS, for_show=True)

        # For each key where the value is None, remove the persisted filter.
        for key, value in filters_dict.items():
            if key in self._nolist_criteria and value is None: # value is True because do_show args are all store_true
                if not args.quiet:
                    self.poutput(f"Removing filterset entry for: '{key}'")
                del self._nolist_criteria[key]
                del self._nolist_funcs[key]

        # Build filter function; return True for PN's that match any 'hide' criterion
        self._nolist_func = lambda pn: any(mf(pn) for mf in self._nolist_funcs.values())
        if not args.quiet:
            self.poutput('Current filters:  '+str(self._nolist_criteria))



    # map COMMAND  ---------------------------------------------------------------------
    map_description = ("""
Change the mapping from Python objects to Pobshell namespaces
    
members (what gets mapped): 
    attributes: Map object attributes
    contents: Map contents of collection objects such as lists & dicts 
    everything: Map object attributes and contents

binding (how attributes are mapped):  
    dynamic: Get attributes with vars(), or dir() and getattr()
    static:  Get attributes from __dict__ entries without resolving descriptors         

resolution (where attributes come from)
    mro: Attributes found via class hierarchy (dir-style)
    local: Only attributes defined directly on the object

frames (how frame objects are mapped):
    framesattrs: Map attributes of Frame objects  
    variables: Map Frame members as dict of their globals & locals            
    """)

    map_parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter, description=map_description)
    # map_parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter, epilog=map_epilog)

    map_parser.add_argument('map_pref1', nargs='?', choices=PobPrefs.map_option_names)
    map_parser.add_argument('map_pref2', nargs='?', choices=PobPrefs.map_option_names, help=argparse.SUPPRESS)
    map_parser.add_argument('map_pref3', nargs='?', choices=PobPrefs.map_option_names, help=argparse.SUPPRESS)
    map_parser.add_argument('map_pref4', nargs='?', choices=PobPrefs.map_option_names, help=argparse.SUPPRESS)
    map_parser.add_argument('-q', '--quiet', action='store_true', help="don't echo map change to output")


    @cmd2.with_argparser(map_parser)
    def do_map(self, args):
        """Change how Python objects map to Pobshell paths"""

        def process_preference(pref):
            if not pref:
                return
            if pref == 'everything':
                PobPrefs.contents = True
                PobPrefs.attributes = True
            elif pref == 'attributes':
                PobPrefs.contents = False
                PobPrefs.attributes = True
            elif pref == 'contents':
                PobPrefs.contents = True
                PobPrefs.attributes = False
            elif pref == 'static':
                PobPrefs.static = True
            elif pref == 'dynamic':
                PobPrefs.static = False
            elif pref == 'mro':
                PobPrefs.mro = True
            elif pref == 'local':
                PobPrefs.mro = False
            elif pref == 'frameattrs':
                PobPrefs.simpleframes = False
            elif pref == 'variables':
                PobPrefs.simpleframes = True

        if not (args.map_pref1 or args.map_pref2 or args.map_pref3 or args.map_pref4):
            # no new map parameters so output curr settings and return
            self.poutput(PobPrefs.map_description())
            return

        oldmap = PobPrefs.map_description()
        process_preference(args.map_pref1)
        process_preference(args.map_pref2)
        process_preference(args.map_pref3)
        process_preference(args.map_pref4)

        if not args.quiet:
            self.poutput('map - was: ' + oldmap)
            self.poutput(' - now: ' + PobPrefs.map_description())



    # ======================================================================================
    # ## utility COMMANDs =====================================================================
    # ======================================================================================


    # eval COMMANDs  ---------------------------------------------------------------------

    def do_eval(self, args):
        """Evaluate or execute a Python expression (rest of the line) in namespace of current object

        - Changes to mutable objects affect the original object in the calling frame
        - Changes to Pobshell's root namespace are persisted in Pobshell, but don't affect calling frame
        - Other eval changes aren't persisted.
         """

        # """Evaluate Python expression in current namespace"""
        # Dynamic evaluation of expressions within the context of an object's attribute namespace, treating its attributes as local variables.

        # args = self.recover_contentkeyed_argstr(args)
        out_type, res = self.curr_path.eval_PYEXPR(pyexpr=args)
        if out_type == 'eval':
            self.poutput(pprint.pformat(res))


    def do_rooteval(self, args):
        """Evaluate or execute Python code (the rest of the line) in root namespace

        - Shortcut for this command is '::'
        - If executing code changes mutable objects, the original object is changed
            in frame that invoked Pobshell, e.g. appending to a list object  `::l.append(42)`
        - If executing code adds or deletes members from Pobshell root namespace the change
         will be persisted in Pobshell, but won't affect calling frame
            E.g.  `::x = 42`, `::del x`
            N.B. Listing root namespace with `ls` or inspection commands (`cat`, `doc` etc)
             lists added names after sorted listing of original members.  This is intentional.
        - Expressions evaluated at root give same results as in calling frame with default map:
            `members: 'attributes'  binding: 'dynamic'  resolution: 'mro'  frames: 'variables'`
        - Commonly used to
            * import modules on the fly for Pobshell exploration `::import inspect`
            * Explore the result of evaluating an expression `::sx = sympy.sin(x)`
                Here sx will be added to root namespace.  Names used (sympy, x) must be in
                root or, with setting `set global_ns user`, in user_defs.py

         """

        # args = self.recover_contentkeyed_argstr(args)
        out_type, res = self.rootpn.eval_PYEXPR(pyexpr=args)
        if out_type == 'eval':
            self.poutput(pprint.pformat(res))


    def do_py(self, _: argparse.Namespace) -> Optional[bool]:  # pragma: no cover
        """
        Enter an interactive Python shell with current object as namespace
        """
        with self.stacked_command(PobPrefs.map_repr()):  # reset to current map after temporary map setting
            self.onecmd_plus_hooks(f'''map -q attributes''', add_to_history=False)
            with temporary_setting('prettify_infos', False):
                return super().do_py(_)


    # ipython_parser = argparse_custom.DEFAULT_ARGUMENT_PARSER(description="Run an interactive IPython shell")
    # # noinspection PyPackageRequirements
    # @with_argparser(ipython_parser)
    def do_ipy(self, _: argparse.Namespace) -> Optional[bool]:  # pragma: no cover
        """
        Enter an interactive iPython shell with current object as namespace
        """
        with self.stacked_command(PobPrefs.map_repr()):  # reset to current map after temporary map setting
            self.onecmd_plus_hooks(f'''map -q attributes''', add_to_history=False)
            with temporary_setting('prettify_infos', False):
                return super().do_ipy(_)


    # Reuse the same shell parser from cmd2
    shell_parser = cmd2.argparse_custom.DEFAULT_ARGUMENT_PARSER(
        description="Execute a command as if at the OS prompt, with Pobshell command substitution"
    )
    shell_parser.add_argument('command', help='the command to run',
                              completer=cmd2.Cmd.path_complete)
    shell_parser.add_argument(
        'command_args', nargs=cmd2.argparse.REMAINDER,
        help='arguments to pass to command',
        completer=cmd2.Cmd.path_complete
    )

    _AT_RE = re.compile(r'@-?\d+')  # @3  $-2  @$42  @-1 …
    @cmd2.with_argparser(shell_parser, preserve_quotes=True)
    def do_shell(self, args):
        """
        Simple implementation based on args.raw.

        •  ```!sort "" "ls - l"" " -k3```      →
           inner `ls -l` is run in Pobshell, its output captured to a temp file,
           filename substituted, then the OS sees:
           ```sort /tmp/tmp1234 -k3```

        •  ```@N``` / ```$N``` tokens are replaced by temp files containing
           the output obtained from rerunning the N-th history entry.
        """
        self.recover_contentkey_args(args)

        raw = args.cmd2_statement._Cmd2AttributeWrapper__attribute.raw

        # remove the leading alias ('!' or the literal word 'shell ')
        if raw.startswith('!'):
            raw = raw[1:].lstrip()
        elif raw.lower().startswith('shell '):  # user typed: shell …
            raw = raw[6:].lstrip()

        # ────────────────────────────────────────────────────────────
        # Helpers
        # ────────────────────────────────────────────────────────────
        temp_files: list[str] = []
        file_handles: list = []

        def _history_to_file(token: str) -> str:
            """Run history item N (from @N/@-N/$N) and return the temp file path."""
            tmp = NamedTemporaryFile(mode="w+", delete=False, encoding="utf-8")
            file_handles.append(tmp)
            temp_files.append(tmp.name)

            idx = int(token[1:])  # strip first char (@ or $)
            if idx < 1:  # negative indices: -1 is 'current'
                idx -= 1

            if self.history.get(idx).raw.startswith('!') or self.history.get(idx).raw.startswith('shell '):
                raise ValueError(f'History item {idx} is a shell command, and shell does not support recursive calls')# is a shell command

            old_stdout = self.stdout
            old_history_len = len(self.history)
            try:
                self.stdout = tmp
                self.onecmd_plus_hooks(f"history -r {idx}",
                                       add_to_history=False,
                                       raise_keyboard_interrupt=True)

                # Remove any history entry added by this command, to avoid screwing history numbers
                #   used by @N references in this shell command
                while len(self.history) > old_history_len:
                    self.history.pop()

            finally:
                self.stdout = old_stdout
                tmp.flush()
            return "'"+tmp.name+"'"

        def _run_inline(cmdstr: str) -> str:
            """Run *cmd* in Pobshell, capture stdout, return temp file path."""
            tmp = NamedTemporaryFile(mode="w+", delete=False, encoding="utf-8")
            file_handles.append(tmp)
            temp_files.append(tmp.name)

            old_stdout = self.stdout
            old_history_len = len(self.history)

            try:
                self.stdout = tmp
                self.onecmd(cmdstr, add_to_history=False)
                # Remove any history entry added by this command, to avoid screwing history numbers
                #   used by @N references in this shell command
                while len(self.history) > old_history_len:
                    self.history.pop()

            finally:
                self.stdout = old_stdout
                tmp.flush()
            return "'"+tmp.name+"'"

        # ────────────────────────────────────────────────────────────
        # 1.  Scan the raw string once, splitting on every pair of """
        # ────────────────────────────────────────────────────────────
        _TQ = '"""'  # delimiter for triple quoted command substitution blocks
        parts = raw.split(_TQ)
        if len(parts) % 2 == 0:  # odd parts → perfect pairing
            self.perror("Error: unmatched triple quotes")
            return


        _AT_RE = re.compile(r'@-?\d+')  # match @N history references @3, @42, @-1, …
        rebuilt: list[str] = []
        for idx, chunk in enumerate(parts):
            if idx % 2 == 0:  # outside any triple quotes
                # Expand @N / $N
                chunk = _AT_RE.sub(lambda m: _history_to_file(m.group(0)), chunk)
                rebuilt.append(chunk)
            else:  # inside triple quotes
                filename = _run_inline(chunk.strip())
                rebuilt.append(filename)

        final_cmdline = ''.join(rebuilt).strip()

        # ────────────────────────────────────────────────────────────
        # 2.  Execute and clean up
        # ────────────────────────────────────────────────────────────
        try:
            super().do_shell(final_cmdline)
        finally:
            for fh in file_handles:
                try:
                    fh.close()
                except Exception:
                    pass

            for fp in temp_files:
                try:
                    os.unlink(fp)
                except Exception:
                    pass



    # man COMMAND  ---------------------------------------------------------------------

    def man_completer(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:  # pragma: no cover
        """Completes the TOPIC argument of help"""

        # Complete token against topics
        topics = set([os.path.basename(f)[:-4] for f in os.listdir(common.MAN_FOLDER)
                      if f.endswith(".txt") and os.path.isfile(os.path.join(common.MAN_FOLDER, f))])
        strs_to_match = list(topics)
        return self.basic_complete(text, line, begidx, endidx, strs_to_match)


    man_parser = cmd2.Cmd2ArgumentParser(formatter_class=HideArgumentHelpFormatter,
                                         description="")
    man_parser.add_argument(
        'TOPIC', nargs=argparse.OPTIONAL, help="Topic to retrieve help for", completer=man_completer
    )
    man_parser.add_argument('-p', '--paged', action='store_true', help="view output in pager")

    @cmd2.with_argparser(man_parser)
    def do_man(self, arg):
        """Display man pages for a topic; emphasis on examples and use cases

        Restricted to one-word topics
        Outputs slightly prettified text from file:
          MAN_FOLDER/<arg>.txt

        NB Doesn't implement proper markdown because backticks have a special meaning in Pobshell
        Lines starting "# " are an H1 header (bold & underline); # char is stripped
        Lines starting "## " are an H2 header (bold & Italic & underline); ## chars are stripped
        Lines starting "* " are a bullet (bold & italic); '*' char is NOT stripped
        Lines starting "\t" are indented by 4 chars plus they're wrapped and subsequent lines indented to match
        Blank lines are retained

        """

        def render_custom_markdown(md_text: str, indent_spaces: int = 4) -> str:
            try:
                from rich.console import Console
                from rich.text import Text
                from rich.highlighter import NullHighlighter
            except:
                return md_text

            effective_width = PobPrefs.width
            # effective_width = min(PobPrefs.width, 80)
            buffer = StringIO()
            console = Console(file=buffer, force_terminal=True, color_system="truecolor", width=effective_width,
                              highlighter=NullHighlighter())
            lines = []
            for line in md_text.splitlines(keepends=False):
                # My own flavour of (kind-of) markdown
                if line.startswith("# "):  # H1
                    h1 = Text(line[2:].strip(), style="bold underline")
                    lines.append(h1)
                elif line.startswith("## "):  # H2
                    h2 = Text(line[3:].strip(), style="bold italic underline")
                    lines.append(h2)
                elif line.startswith("### "):  # H3
                    h2 = Text(line[4:].strip(), style="bold")
                    lines.append(h2)
                elif line.startswith("* "):  # Bullet point, keep * in string
                    bullet = Text(line, style="bold italic")
                    lines.append(bullet)
                # Blank line
                elif line.strip() == "":
                    lines.append("")  # preserved blank
                # Tab-indented line wraps its text to indented lines
                elif line.startswith("\t"):
                    indent = " " * indent_spaces
                    content = line.lstrip("\t").strip()
                    wrapper_width = effective_width - len(indent)
                    wrapped_lines = Text(content, style='').wrap(console, width=wrapper_width)
                    for i, wrapped_line in enumerate(wrapped_lines):
                        # Add indent to each line
                        wrapped_lines[i] = Text(indent) + wrapped_line
                    lines.extend(wrapped_lines)
                # Append the line unchanged (no markdown processing)
                else:
                    lines.append(line)
                    # lines.append(Markdown(line))  # Screws up code unless code is escaped with backticks,
                                                    # But backticks have meaning in Pobshell so I'd need to escape
                                                    # all the Pobshell backticks

            # Print collected lines to buffer
            for entry in lines:
                console.print(entry)

            return buffer.getvalue()

        topic = getattr(arg, 'TOPIC', None)
        if topic:
            tokens = topic.strip().split()
        else:
            tokens = None

        # has some subtopic supporting code (but subtopics aren't implemented in manpages or parser)
        if not tokens:
            # No input provided; default to the introduction file.
            topic = 'introduction'
            man_file_path = os.path.join(common.MAN_FOLDER, f"{topic}.txt")
        else:
            topic = tokens[0]
            topic_dir = os.path.join(common.MAN_FOLDER, topic)
            if os.path.isdir(topic_dir):
                # The topic exists as a folder.
                if len(tokens) >= 2:
                    # Use the provided subtopic token.
                    subtopic = tokens[1]
                    man_file_path = os.path.join(topic_dir, f"{subtopic}.txt")
                else:
                    # No subtopic provided, so look for a file named topic.txt inside the folder.
                    man_file_path = os.path.join(topic_dir, f"{topic}.txt")
            else:
                # The topic is not a folder; assume a single file named topic.txt exists in MAN_FOLDER.
                man_file_path = os.path.join(common.MAN_FOLDER, f"{topic}.txt")

        if os.path.exists(man_file_path):
            with open(man_file_path, 'r', encoding='utf-8') as f:
                text = f.read()
        else:
            self.perror(f"No manual entry for '{' '.join(tokens)}'.")
            return

        formatted_output = render_custom_markdown(text)
        # Show paged output if -p OPTION is used
        #   or if 'man' command used without TOPIC (as suggested to users in "Welcome" banner)
        if arg.paged or not tokens:
            self.ppaged(formatted_output)
        else:
            self.poutput(formatted_output)




    # exit COMMAND  ---------------------------------------------------------------------

    def do_quit(self, _) -> bool:
        """Quit pobshell gracefully"""
        self.clear_refs()
        return super().do_quit('')


    def exit(self):
        """Quit pobshell gracefully, no args expected"""
        self.clear_refs()
        return super().do_quit('')


    def clear_refs(self):

        del self.root
        # self.root = root  # The Python object providing "root directory" of pobshell "filesystem"

        del self.rootns
        # self.rootns = dirops.PobNS(self.root, abspath='/')  # Persistent Pob namespace for root object

        del self.rootpn
        # self.rootpn = PobNode('/', obj=self.rootns)  # root PobNode; 'obj' attribute references root namespace

        del self.curr_path
        # self.curr_path = self.rootpn

        del self.curr_path_history
        # self.curr_path_history = []

        # del self.py_locals
        # Do I have deleter for this? py_locals is a property
        #   Don't bother, py_locals is only relevant when intropecting, after introspect command



    # sigint COMMAND  ---------------------------------------------------------------------

    def do_killsession(self, arg):
        """Kill Python session """
        if PobPrefs.DEBUG:
            sys.exit(1)
        else:
            raise RuntimeError("Error 'killsession' command is invalid outside debug mode")


    def do_die(self, arg):
        """Exit pobshell and prevent further use until pobshell.reset().

        Use 'die' to fully halt the session. pobshell won't respond to shell() or pob()
        until pobshell.reset() is used
        """
        self.exit_code = POB_HALT
        self.pfeedback("Exiting pobshell (halted). To use it again, call pobshell.reset()")
        return True


    # breakpoint COMMAND  ---------------------------------------------------------------------

    def do_break(self, args):
        """Get a debug prompt """
        self.poutput("Entering debugger; Enter 'c' (continue) to return to pobshell cmdloop")
        breakpoint()

    # introspect COMMAND  ---------------------------------------------------------------------

    # add pob objects to rootns
    def do_introspect(self, args):
        """Add pob objects to rootns """
        modules = {'pobshell': sys.modules['pobshell'], 'pobmain': sys.modules['pobshell.pobmain']}
        for name, module in modules.items():
            self.rootns[name] = module

        # Add a reference to self, a Pobiverse instance
        # +++ WARNING, POBSHELL DEBUGGING ONLY: Lots of recursion crashes in this namespace
        self.rootns['PVi'] = self


    # breakpoint COMMAND  ---------------------------------------------------------------------

    def do_newline(self, args):
        """Output a blank line; for formatting results of find --cmd """
        self.poutput()


    # comment COMMAND  ---------------------------------------------------------------------

    def do_comment(self, arg):
        """Write multiline comment text to command history. End comment with ';' """
        pass


    # def do_noted(self, args):
    #     """List comments found in command history, each with the command that preceeded it"""
    #     self.onecmd_plus_hooks(r'''history -a | egrep -B 1 "\d+\s+##"''', add_to_history=False, raise_keyboard_interrupt=True)



    # ==========================================================================================
    # ## info COMMANDs & helper methods ======================================================
    # ==========================================================================================

    # Helper methods -----------------------------

    def pobnodes_for_target(self, target_pattern: str, exclude_func=None) -> Union[None, list[PobNode]]:
        """Retrieve a list of PobNodes matching a given target pattern.

        Handles various target pattern scenarios, including wildcards, relative paths, and absolute paths.
        Applies an optional exclusion function to filter the results.

        Args:
            target_pattern: The pattern to match against PobNode names. Can include wildcards.
            exclude_func: An optional function to exclude specific PobNodes from the result.

        Returns:
            A list of matching PobNodes, or None if an error occurs or no nodes match.
        """
        if target_pattern is None:
            target_pattern = ''
        else:
            target_pattern = target_pattern.strip()

        # Handle common cases efficiently
        if target_pattern == '.':
            if self.curr_path.abspath == "/":
                target_pattern = "/."
            else:
                return [self.curr_path]

        if target_pattern == '':
            return list(self.curr_path.filtered(target_name_pattern='*', automagic=True, exclude_func=exclude_func))

        # Handle trailing slash (implies matching all members)
        if not target_pattern or (not ('*' in target_pattern or '?' in target_pattern)
                                  and target_pattern.endswith('/')):
            automagic = True
            target_pattern += '*'
        else:
            automagic = False

        if target_pattern == '$$':
            return [PobNode(abspath, self.rootpn) for abspath in self._result_paths]

        path_pattern = self.normpath(target_pattern)

        # Handle normalized path scenarios
        if path_pattern == self.curr_path.abspath:
            return [self.curr_path]
        elif path_pattern == '/':
            return [PobNode('/', self.rootpn)]

        patn_head, patn_tail = strpath.split(path_pattern)

        if '*' in patn_head or '?' in patn_head:
            self.perror("Wildcards are not supported in parent path of TARGET patterns")
            return None

        # Determine head PobNode
        if patn_head == self.curr_path.abspath:
            headpn = self.curr_path
        else:
            headpn = PobNode(patn_head, self.rootpn)

        # Handle literal tail patterns
        if not ('*' in patn_tail or '?' in patn_tail):
            return [PobNode.init_from_parent(headpn, patn_tail)]

        return list(headpn.filtered(patn_tail, automagic, exclude_func))


    def output_path_banner(self, namestr, plain=False):
        # Output a banner heading for each path, used by multi-line info commands such as cat, doc or ls -x
        #   NB styled after linux "head" command's output banner
        #   if plain is True, style it after linux "ls" command's output banner
        styled_namestr = cmd2.ansi.style(namestr, fg=Fg[PobPrefs.current_theme['banner']])
        if plain:
            self.poutput(f"\n{styled_namestr}:")
        else:
            self.poutput(f"# ==> {styled_namestr} <==")


    def output_infos(self, cmdstr: str, args, exclude_func: Callable, infocmd_func: Union[Callable, None] = None) -> None:
        """
        Generate matching paths from curr_path, apply infocmd_func to each, output formatted result

        Matching paths are generated by glob pattern matching of member name, then filtered by exclude_func
        Apply one or more pob commands.  Usually one, but "ls -x" invokes other infocommands

         Formatting results:
           One row of output per pn (pn is a pobnode object representing a matching path)
               ls -l wants a row of infos per pn: (pn.name | pn.abs, xtra_safe_repr(pn.obj), pn.type)
               ls -1 wants a single info as a row, per pn: (pn.name | pn.abs)
               infocommands with  -1 want a single row per pn of (pn.name | pn.abs, truncate(infofunc(pn.obj)))

           Multiple rows per pn & possibly a banner
               ls -x and pathinfo apply multiple pob commands to each pn, output is one row per command
               infocmds without -1 give multiple rows/lines from a single pob command application

           Columnize: Multiple rows for multiple pns (each results from a single pob command)
               ls applies single infofunc to ach pn (pn.name) and the list of result values displayed columnized

           :args: cmd2 object representing command string with its options
           :cmdstr: string representation of command being applied
           :exclude_func: Python function to filter out unwanted objects
           :infocmd_func: Python function expecting a pobnode object as argument; executes the command & returns info

         """

        # TODO move these hardcoded strings to infocmd, so they live beside INFOCMD_SPECS
        arg_oneline = getattr(args, argstr_oneline, False)
        arg_long = getattr(args, argstr_long, False)
        arg_xtralong = getattr(args, argstr_xtralong, False)
        arg_numlines = getattr(args, argstr_numlines, None)
        arg_paged = getattr(args, argstr_paged, False)
        arg_enumerate = getattr(args, argstr_enumerate, False)
        arg_verbose = getattr(args, argstr_verbose, False)
        arg_pypath = getattr(args, argstr_pypath, False)

        arg_quiet = getattr(args, argstr_quiet, False)
        # N.B. arg_all, OPTION  -a is now handled by imethods

        arg_pattern = getattr(args, argstr_TARGET, None)

        # get pns that match the target pattern
        try:
            targetpns = self.pobnodes_for_target(arg_pattern, exclude_func=exclude_func)
        except dirops.PobMissingMemberException:
            head, _ = strpath.split(arg_pattern)
            if '*' in head:
                self.perror(f'{cmdstr}: {arg_pattern}: Wildcards are not supported in parent path')
            else:
                self.perror(f'{cmdstr}: {arg_pattern}: No such path')
            return

        # some commands expand the list of pn targets
        if cmdstr == 'pathinfo':
            newpns = []
            for pn in targetpns:
                splitpath = strpath.split_path_all(pn.abspath)[1:]  # strip off blank name corresponding to root
                for subpathlen in range(len(splitpath)):
                    extrapn_path = strpath.join('/',*splitpath[:subpathlen+1])
                    newpns.append(PobNode(extrapn_path, self.rootpn))
            targetpns = newpns

        if not targetpns:
            return

        # we'll stop after matching arg_LIMIT pns
        arg_LIMIT = getattr(args, argstr_LIMIT, None)

        # define non-enumerated path display functions
        #  used in max_col0_width calculation even for enumerated paths
        if arg_verbose:
            path_attribute = 'abspath'
        elif arg_pypath:
            path_attribute = 'pypath'
        else:
            path_attribute = 'name'

        # A function to return possibly truncated string listing abspath|pypath|name for node
        #   _noE because it is used for displayed path string when no enumerate option was chosen
        path_func_noE = lambda pn: short(getattr(pn, path_attribute))

        if arg_enumerate:
            # define path functions that enumerate paths
            self._result_paths = []
            # a bit of 'or' trickery to append the abspath path as well as return appropriate path string for output
            path_func = lambda pn: (self._result_paths.append(pn.abspath)
                                    or boldit(str(len(self._result_paths)-1)) + ': ' + short(getattr(pn, path_attribute)))
        else:
            path_func = path_func_noE

        # Easy special case: "ls" WITHOUT "-l", "-1" or "-x" outputs columnized names or abspaths
        if cmdstr == 'ls' and not (arg_oneline or arg_long or arg_xtralong):
            self.columnize([path_func(pn) for pn in targetpns[:arg_LIMIT]],
                           display_width=PobPrefs.width)
            return

        tbl = None  # RunningTable object to handle row oriented output

        styles = None
        max_col0_width = None

        if arg_oneline or (arg_long and not arg_xtralong):  # -1  or -l
            # set up styles & col0 width for row oriented output (one row per pn)
            #   handles  "INFOCMD -1", "ls -1", and "ls -l"

            if cmdstr == 'ls':
                # "ls -1" has no style (i.e. None), "ls -l" has [path-style, type-style, no-style]
                if arg_long:
                    styles = PobPrefs.lsl_styles
                    infocmd_func = lambda pn: PobPrefs.lsl_func(pn, path_func=path_func, is_verbose=arg_verbose)

                else:
                    infocmd_func = lambda pn: [path_func(pn)]
                max_col0_width = (max([ansi.style_aware_wcswidth(path_func_noE(pn)) for pn in targetpns[:arg_LIMIT]])
                                  + (len(str(len(targetpns[:arg_LIMIT]))) + 2 if arg_enumerate else 0))
            else:
                # "<infocmd> -1 -q" gives [line]   -- style = None
                # "<infocmd> -1" as lsx_context gives ['    '+cmdstr, line]  --  style = None
                # otherwise "<infocmd> -1" gives [path, line]  -- style = [path-style, no-style]

                if self.lsx_context:  # ls -x subcommand
                    max_col0_width = 16  # 4 + len(cmdstr)
                elif arg_quiet:
                    max_col0_width = PobPrefs.width    # no path is output, so col0 is the infocmd result
                else:   # infocmd -1 gives [path, line]  infocmd -l gives multiline [path, line]
                    styles = [{'fg': Fg[PobPrefs.current_theme['path']]}, {'fg': Fg[PobPrefs.current_theme['value']]}]
                    max_col0_width = (max([ansi.style_aware_wcswidth(path_func_noE(pn)) for pn in targetpns[:arg_LIMIT]])
                                      + (len(str(len(targetpns[:arg_LIMIT]))) + 2 if arg_enumerate else 0))


        if max_col0_width is not None:
            tbl = RunningTable(max_col0_width, styles)


        # CORE LOOP TO EVALUATE INFOCMD OVER TARGET POBNODES ----------------------------------------
        pn_num = 0
        for pn in targetpns:
            if arg_LIMIT is not None and pn_num >= arg_LIMIT:
                return

            # handle "ls -x" and "pathinfo" which invoke multiple cmds on each pn
            #   lsx_cmds = ['ls -l', 'type -1', 'signature -1', 'predicates -1', 'doc -1', 'mro -1', ...]
            if (cmdstr == 'ls' and arg_xtralong) or cmdstr == 'pathinfo':
                lsx_cmds = PobPrefs.lsxv_cmds if arg_verbose else PobPrefs.lsx_cmds
                with temporary_setting('lsx_context', True, self):
                    # run each ls -x subcommand on this pobnode
                    for cmd in lsx_cmds:
                        # NB don't clobber history with sub commands
                        #   and ls -x of / mustn't give ls -x of all the members of root
                        if self.onecmd_plus_hooks(f'''{cmd} "{'/.' if pn.abspath == '/' else pn.abspath}"''',
                                                  add_to_history=False,
                                                  raise_keyboard_interrupt=True):
                            return  # stop running if onecmd_plus_hooks returns True
                pn_num += 1
                continue

            output = infocmd_func(pn)

            # Check for NoSuchInfo objects, and turn them into strings or skip this pn
            if isinstance(output, common.NoSuchInfo):
                if PobPrefs.missing == MissingInfoOptions.skip_item:
                    continue
                else:
                    if PobPrefs.missing == MissingInfoOptions.exception_string:
                        output = "Exception::" + str(output)
                    else:
                        output = ''  # PobPrefs.missing == MissingInfoOptions.empty_string

            # handle string output from non-ls infocmd; maybe styled, maybe multiline
            if isinstance(output, str):

                if arg_paged and pn_num == 0:  # pragma: no cover
                    # -p option as applied here invokes cmd2 pager on first infocmd result only
                    #    to avoid risk of user having to quit a pager for each member
                    self.output_path_banner(path_func(pn))
                    self.ppaged(output)
                    pn_num += 1
                    continue

                if PobPrefs.flatten_multiline:
                    lines = [output.replace('\n', '\\n')]
                else:
                    lines = str(output).splitlines()[:arg_numlines]

                if not arg_oneline:  # multi line; we have infocmd without -1

                    # Split multiline output string into a list of lines & apply "-n" option truncation, if any
                    #   N.B. Lines are based on newline chars rather than terminal width

                    # Multiple line output for each pn; add a banner above first line of results for each pn
                    #     unless we have "-v" verbose option, which adds an abspath prefix to each output line

                    for linenum, line in enumerate(lines):
                        if arg_long:
                            # infocmd -l  means lines are prefixed with paths instead of using a banner
                            self.poutput(f"{style_str(path_func(pn), 'path')} {line} ")
                        else:
                            # output a banner (unless -q)
                            if linenum == 0:
                                if not arg_quiet:
                                    self.output_path_banner(path_func(pn))
                            self.poutput(line)

                    # Follow the last line of each pn's multiline output with a blank line,
                    # unless the -q (quiet) option is used — in that case, the user is likely
                    # counting lines and doesn't want blanks interfering.
                    if not arg_quiet:
                        self.poutput()

                    pn_num += 1
                    continue  # on to the next pn

                else:  # one liner
                    # The "-1" option requires truncation to one line (terminal width!)
                    #   So we process these as lists with RunningTable.row
                    line = lines[0] if lines else ''
                    if self.lsx_context:
                        output = ['    ' + cmdstr, line]
                    else:
                        if arg_quiet:
                            output = [line]
                        else:
                            output = [path_func(pn), line]

            # Use RunningTable to process the lists we got from a "ls -1" or "ls -l" command,
            #   or from a row-oriented one liner above
            if isinstance(output, (list, tuple)):
                self.poutput(tbl.row(output))
            else:
                if PobPrefs.DEBUG:
                    # trap PobNode infoproperty coding errors
                    raise TypeError(f"Unexpected output type for '{cmdstr}: {arg_pattern}'")
                else:
                    self.poutput(str(output))
            pn_num += 1


    # tree COMMAND  ---------------------------------------------------------------------

    tree_parser = argparse.ArgumentParser(formatter_class=HideArgumentHelpFormatter)
    tree_parser.add_argument('-d', '--depth', type=int, help='Depth of tree (default is 2)')
    tree_parser.add_argument('-n', '--numlines', type=int, help='truncate at N lines per entry')
    tree_parser.add_argument('-a', '--all', action='store_true', help='include hidden prefixes')
    tree_parser.add_argument('-o', '--or', '--any', action='store_true',
                             help="Include objects that satisfy ANY match criteria")
    tree_parser.add_argument('-v', '--verbose', action='store_true', help="echo fullpath to output")
    tree_parser.add_argument('-p', '--paged', action='store_true', help="view output in pager")
    tree_parser.add_argument('--prune', nargs='+', help='Prune paths matching abspath pattern, typename or satisfying predicate')
    tree_parser.add_argument('path', metavar='PATH', completer=ns_path_complete, help="Specify the target (name or path)",
                             suppress_tab_hint=True)

    @cmd2.with_argparser(tree_parser)
    def do_tree(self, args):
        """Tree diagram of object, and members satisfying [MATCH CRITERIA], to depth N"""
        self.recover_contentkey_args(args)

        filters_dict = extract_filter_criteria(args, infocmds.INFOFILTERS, for_show=False)
        if getattr(args, 'or'):
            match_func = None if len(filters_dict) == 0 else lambda pn: any(func(pn) for (_, func)
                                                                            in filters_dict.values() if func is not None)
        else:
            match_func = None if len(filters_dict) == 0 else lambda pn: all(func(pn) for (_, func)
                                                                            in filters_dict.values() if func is not None)

        exclude_func = None if args.all else self._nolist_func  # prune_prematch


        if getattr(args, 'prune', None):
            # convert prune args to functions in the prune_funcs list
            prune_funcs = []
            for pn in getattr(args, 'prune', ''):

                self.add_prune(pn, prune_funcs)
            # convert prune_funcs list to a lambda func
            base_prune_func = lambda pn: any(pf(pn) for pf in prune_funcs)
        else:
            base_prune_func = None

        # Update prune function with any args like --CODE, --DATA that have a pruneset name
        prune_func = base_prune_func
        pruneset_map = None

        for pruneset_name in PobPrefs.prunesets.keys():
            if getattr(args, pruneset_name, None):
                if base_prune_func is None:
                    prune_func = PobPrefs.prunesets[pruneset_name]
                else:
                    prune_func = lambda pn: base_prune_func(pn) or PobPrefs.prunesets[pruneset_name](pn)
                pruneset_map = PobPrefs.pruneset_maps[pruneset_name]
                break  # only support one pruneset at a time for now

        # stacked_command guarantees to return map to prior setting after code block executes even if exception occurs
        with self.stacked_command(PobPrefs.map_repr()):

            # set the temporary map(s)
            #   if pruneset has an associated map, apply that first
            #   if user has specified a map, apply that second
            if pruneset_map:
                self.onecmd_plus_hooks(f'''map -q {pruneset_map}''', add_to_history=False)
            if getattr(args, 'map', None) is not None:
                self.onecmd_plus_hooks(f'''map -q {args.map}''', add_to_history=False)

            # Identify PobNode that's root of the tree
            # N.B. default to current path if no path given
            if hasattr(args, 'path'):
                objpath = args.path
            else:
                objpath = self.curr_path
            try:
                objpath = self.normpath(objpath)
                pn = PobNode(objpath, self.rootpn)  # objnode.obj is the python object at the path given
            except dirops.PobMissingMemberException:
                self.perror(f'tree: {args.path}: No such path')
                return
            for line in pn.tree(depth=args.depth if args.depth is not None else 2,
                                match_func=match_func,
                                exclude_func=exclude_func,
                                prune_func=lambda node: prune_func and prune_func(node) and node.abspath != pn.abspath):
                                # prune_func=lambda node: prune_func(node) and node.abspath != pn.abspath):
                                # prune_func=prune_func):

                self.poutput(truncate_line(line, PobPrefs.width))


    def add_prune(self, prune_str, prune_func_list, args=None):

        # given a prune_str, append to prune_func_list a function that tests a PobNode against the prune
        #   NB must be pn because I need to test pn.abspath
        # Args:
        #   prune_str
        #     if it contains '/' it's treated as a pattern for an abspath to prune
        #     if it starts with 'is', it's a filter name: isdata, or inspect.is*
        #     if it starts with 'nis', it's a negated filter name: not isdata(obj); or not inspect.is*(obj)
        #     otherwise its taken to be a typename: list, str, type, module, Bunch, Symbol etc
        if '/' in prune_str:
            # prune_str is an abspath pattern
            if args:
                # find provides us an args object that may specify options for case sensitivity or regex
                prune_func_list.append(make_match_func('abspath', prune_str, negated=False, args=args))
            else:
                # tree gives us no args object as it has no -i or -r options; use standard globbing
                prune_func_list.append(lambda pn: fnmatch.fnmatchcase(str(pn.abspath), prune_str))

        elif prune_str.startswith('is'):
            # it's a predicate function
            prune_func_list.append(lambda pn: PobPrefs.available_filters[prune_str](pn.obj))  # expects an obj
        elif prune_str.startswith('nis'):
            # it's a negated predicate function
            prune_func_list.append(lambda pn: not PobPrefs.available_filters[prune_str[1:]](pn.obj))  # expects an obj
        else:
            # it's a typename
            if args:
                prune_func_list.append(make_match_func('typename', prune_str, negated=False, args=args))
            else:
                prune_func_list.append(lambda pn: type(pn.obj).__name__ == prune_str)



    # ==========================================================================================
    # ## test suite commands  ============================================================================
    # ==========================================================================================

    # TODO test stuff is all kludgy and horrible, and designed
    #  to support multiple transcripts - one per Use_Case file.
    #  But that facility is not used currently

    def _run_transcript_tests(self, transcript_paths: List[str]) -> None:
        # override cmd2's _run_transcript_tests, just to set perror_to_poutput to True,
        #   so testing will check perror alongside poutput
        with temporary_setting('perror_to_poutput', True, self):
            return super()._run_transcript_tests(transcript_paths)


    def do_reset(self, args):
        """Reset pob state: Exit Pobiverse cmdloop & restart with same arguments"""
        self.perror("Reset")
        self.exit_code = POB_CONTINUE
        return True


    def _generate_transcript(self, history: Union[List[HistoryItem],
                             List[str]], transcript_file: str, **kwargs) -> None:  # pragma: no cover
        with temporary_setting('allow_style', cmd2.ansi.allow_style.NEVER, self), \
                temporary_setting('perror_to_poutput', True, self):
            super()._generate_transcript(history, transcript_file, **kwargs)

        try:
            with open(os.path.abspath(os.path.expanduser(transcript_file)), 'r') as transcript_input:
                transcript_in = transcript_input.read()
        except OSError as ex:
            self.perror(f"Error reading transcript file '{transcript_file}': {ex}")
            return

        pattern = r" at 0[xX][0-9a-fA-F]+"
        replacement = r" at /0[xX][0-9a-fA-F]+/"
        transcript_out = re.sub(pattern, replacement, transcript_in)

        try:
            with open(os.path.abspath(os.path.expanduser(transcript_file)), 'w') as transcript_output:
                transcript_output.write(transcript_out)
        except OSError as ex:
            self.perror(f"Error saving transcript file '{transcript_file}': {ex}")



    test_parser = argparse.ArgumentParser()
    test_parser.add_argument('ACTION', nargs=1, choices=['init', 'show', 'cats', 'catt', 'load', 'edit', 'run', 'regenerate'],
                             help="[init: Initialise new testsuite,  " +
                                  "show: List collected cmds not yet written,  " +
                                  "cats: Show contents of current script,   " +
                                  "catt: Show contents of current transcript,   " +
                                  "load: Load existing testsuite script,   " +
                                  "edit: Edit current script,   " +
                                  "run:  Run tests in current transcript,   " +
                                  "regenerate:  Regenerate transcript from current script ")
    test_parser.add_argument('PATH', type=str, nargs='?', help="load testsuite script", const = '')


    @cmd2.with_argparser(test_parser)
    def do_test(self, args):   # pragma: no cover

        # prevent test scripts from clobbering history
        self.persistent_history_file = ''

        if args.ACTION[0] == 'init':
            self.pfeedback("init")
            # check if test script generation is in progress, if not, then start one
            self.test_collector = self.TestCollector(self, self.root, self.history)
            self.test_collector.start_collecting()

        elif args.ACTION[0] == 'load':
            self.pfeedback("load")
            self.test_collector = self.TestCollector(self, self.root, self.history)
            self.test_collector.load_test(args.PATH)
            self.test_collector.start_collecting()

        elif args.ACTION[0] == 'edit':
            self.pfeedback("edit script")
            self.onecmd_plus_hooks(f"edit '{self.test_collector.script_path}'")

        elif args.ACTION[0] == 'show':
            self.pfeedback("show cmd collection")
            self.test_collector.show_cmd_collection()

        elif args.ACTION[0] == 'cats':
            self.pfeedback("cat script")
            self.test_collector.cat_script()

        elif args.ACTION[0] == 'catt':
            self.pfeedback("cat transcript")
            self.test_collector.cat_transcript()

        elif args.ACTION[0] == 'run':
            self.pfeedback("run")
            self.test_collector.test_transcript()

        elif args.ACTION[0] == 'regenerate':
            self.pfeedback("regenerating transcript")
            self.test_collector.generate_transcript()


    class TestCollector:  # pragma: no cover
        state_change_cmds = ['cd', 'cdh', 'set', 'show', 'hide', 'unhide', 'prune', 'unprune', 'map', 'mount', 'unmount']
        # can't test state_change_cmds directly, addtest (§) the 'pwd' or other command that follows
        state_change_cmd_regex = [r'^\s*'+cmd for cmd in state_change_cmds]

        def __init__(self, pob, rootframe, history):
            # rootframe: PV.root
            # history: PV.history

            self._pob = pob  # keep a reference to Pobiverse instance, so TestCollector can run scripts etc

            self.usecase_abspath = inspect.getframeinfo(rootframe, context=1).filename

            self.history = history
            self.start_index = len(history)  # first index at which collection of state change cmds starts
                                             #      - initialise with current cmd index; "test init" or 'test load"
                                             # NB test init isn't a state change, nor is test load

            self._script_path = None  # from loaded testcollection path, or derived from self._test_id when generating a script
            self._test_id = None  # derived from loaded testcollection name, or generated by test init command

            self.collected_cmds = None
            self.uuid = None


        def start_collecting(self):
            self.collected_cmds = []
            self.start_index = len(self.history)  # index of curr cmd, at which collection of state change cmds starts
            self._pob.pfeedback(f"Ready for test collection, starting index {self.start_index}")


        def add_test(self):
            # collect state changes since self.start_index; then addtest with comment from curr_cmd and cmd from prev_cmd

            # Don't add test if cmd is:  test, addtest or state change cmd
            i = len(self.history)
            test_cmd = self.history.get(i - 1)
            nocapture_cmds = ['run_script', 'test']
            nocapture_cmds.extend(self.state_change_cmds)
            if any([test_cmd.raw.strip().startswith(x) for x in nocapture_cmds]):
                raise ValueError(f"addtest: Can't add test for cmd: {test_cmd}")

            # go ahead and add test
            self.collect_state_changes()
            self.collect_comment_and_cmd()
            self.update_script()
            self.cat_script()
            self.generate_transcript()  # it'll overwrite the old one if it exists, but that's ok
            self.cat_transcript()
            self.test_transcript()



        @property
        def usecase_nameonly(self):
            # filename without path
            return os.path.basename(self.usecase_abspath)

        @property
        def usecase_namecore(self):
            # filename without extension or path
            return os.path.splitext(self.usecase_nameonly)[0]

        @property
        def script_dir(self):
            if self._script_path:
                script_dir, script_nameonly = os.path.split(self._script_path)
            # if no directory was given for test script, use "Transcript_Tests"
            #   relative path depends on the working directory where pob.shell was invoked
            elif os.getcwd().endswith('Use_Cases'):
                script_dir = '../Transcript_Tests/'
            else:
                script_dir = 'Transcript_Tests/'
            return script_dir


        def load_test(self, script_path=''):
            # script_path: name or fullpath of script or transcript; or empty string
            #   script_path of None or '' will load most recent testcollection for current usecase file

            script_dir, script_nameonly = None, None

            # if test collection is in progress? overwrite?
            # if script path for script_ or transcript_ was provided use that
            if script_path:
                script_dir, script_nameonly = os.path.split(script_path)
                if script_nameonly.startswith('transcript'):
                    script_nameonly = script_nameonly[4:]  # script filename is just transcript filename minus 4 chars
                self._script_path = os.path.join(script_dir, script_nameonly)
            # if no script_path was given, get the most recent test script for this usecase file
            else:
                script_paths = glob.glob(os.path.join(self.script_dir, f'script_{self.usecase_namecore}_*.txt'))
                latest_script = max(script_paths, key=os.path.getmtime)
                self._script_path = latest_script

            # ok, we have script_path, now run it to catch up current state to end state for script
            #   so we can execute cmds and append them to script
            self._run_script()

            self._pob.pfeedback(f"Loaded test {self.script_path}")


        def _run_script(self):
            # Playback script, to catch up current pob state to final testsuite state
            #   We don't want to run scripts we've just written; only run scripts when loading
            #   so we have the right state to append more tests

            assert self.script_path

            # Prevent addtest from collecting cmds during script playback
            self.collected_cmds = None

            with self._pob.stacked_command(f'set echo {self._pob.echo}'):
                # feedback_freq
                self._pob.onecmd_plus_hooks(f"set echo true", add_to_history=False)
                self._pob.pfeedback(f"running script {self.script_path}")
                self._pob.onecmd_plus_hooks(f"run_script {self.script_path}")


        @property
        def script_path(self) -> str:
            if self._script_path:
                return self._script_path
            this_dir = os.path.dirname(__file__)
            return os.path.join(this_dir, "../Transcript_Tests", f"script_{self.usecase_namecore}_{self.test_id}.txt")


        @property
        def test_id(self):
            if not self._test_id:
                if self._script_path:
                    script_dir, script_nameonly = os.path.split(self.script_path)
                    script_name_noext, _ = os.path.splitext(script_nameonly)
                    self._test_id = script_name_noext[-32:]  # uuid in string form is 32 hex digits
                else:
                    self._test_id = uuid.uuid4().hex
            return self._test_id


        @property
        def transcript_path(self) -> str:
            if self._script_path:
                script_dir, script_nameonly = os.path.split(self.script_path)
            this_dir = os.path.dirname(__file__)
            return os.path.join(this_dir, "../Transcript_Tests", f"transcript_{self.usecase_namecore}_{self.test_id}.txt")


        def _get_state_change_history(self, start_index):
            # capture state changing commands to history_subset for all >= start_index (1-based)
            regex = '|'.join(self.state_change_cmd_regex)
            history_subset = self.history.regex_search(regex)
            for k, v in list(history_subset.items()):
                if k < start_index:
                    del history_subset[k]
            res = []
            for k in sorted(history_subset.keys()):
                res.append((k, history_subset[k]))
            return res


        def collect_state_changes(self):
            # collect all state change commands since last command was collected, or test collection was initialised/loaded
            cmd_list = self._get_state_change_history(self.start_index)
            if not self.collected_cmds:
                self.collected_cmds = []
            self.collected_cmds.extend(cmd_list)


        def collect_comment_and_cmd(self):
            # save the two most recent cmds in history to collected_cmds
            #   but transpose them in collected_cmds, so comment comes *before* the cmd it references.
            i = len(self.history)
            curr_cmd = self.history.get(i)
            prev_cmd = self.history.get(i - 1)
            self.collected_cmds.append((i, curr_cmd))
            self.collected_cmds.append((i - 1, prev_cmd))



        def update_script(self):
            with open(self.script_path, 'a') as script:
                for index, item in self.collected_cmds:
                    script.write(f"{item.raw}\n")
            self.start_collecting()


        def show_cmd_collection(self):
            print("TC.collected_cmds")
            print(f"Current test id {self.test_id}")
            pprint.pprint([(k, v.raw) for k, v in self.collected_cmds])


        def cat_script(self):
            out = subprocess.run(["cat", self.script_path], capture_output=True)
            print(f'CAT SCRIPT: {self.script_path}')
            print(str(out.stdout, encoding="utf8"))
            print("---")
            print()


        def cat_transcript(self):
            out = subprocess.run(["cat", self.transcript_path], capture_output=True)
            print(f'CAT TRANSCRIPT: {self.transcript_path}')
            print(str(out.stdout, encoding="utf8"))
            print("---")
            print()


        def generate_transcript(self):
            transcript_cmd = ' '.join(["python", f"{self.usecase_abspath}",
                                       f"'run_script  {self.script_path} -t {self.transcript_path}' 'killsession'"])
            print("GENERATING TRANSCRIPT: ")
            print("<<")
            print(transcript_cmd)
            print(">>")

            out2 = subprocess.run(args=transcript_cmd, capture_output=True, timeout=600, shell=True, text=True)
            print(out2.stdout)
            print(out2.stderr)
            print("---")


        def test_transcript(self):
            runtest_cmd = f"python {self.usecase_abspath} --test {self.transcript_path}"
            print(f"TESTING TRANSCRIPT:")
            print("<<")
            print(runtest_cmd)
            print(">>")

            out3 = subprocess.run(args=runtest_cmd, capture_output=True, timeout=600, shell=True, text=True)
            print(out3.stdout)
            print(out3.stderr)
            print("---")


        def cat_transcript(self):
            print(f"TRANSCRIPT: {self.transcript_path}")
            with open(self.transcript_path, 'r') as transcript:
                print(transcript.read())
            print("---")


    def do_addtest(self, args):
        """Add previous command and its output, and any state changes since last addtest, to test script """

        self.recover_contentkey_args(args)

        # Don't add tests during script playback
        if self.in_script() or self.test_collector is None or self.test_collector.collected_cmds is None:
            return

        # Add §-comment and the cmd it refers to
        self.test_collector.add_test()
        print("---")
        print("Back to current session..")
        return



    find_parser = cmd2.Cmd2ArgumentParser(formatter_class=HideArgumentHelpFormatter,
                                          description=
                                          "Search objects recursively",
                                          epilog=("NEGATED FILTERS: Negate filters by adding n, e.g. --nisdata, --nabspath PATTERN\n"))

    find_parser.add_argument('path', nargs='?', metavar='PATH', help='path of object to search (optional)',
                             completer=ns_path_complete, suppress_tab_hint=True)

    # N.B. !! other kinds of filter args are added in Pobiverse.__init__ after PobPrefs.load_settings has picked up
    #   additional definitions from user_defs.py


    # match actions
    find_action_group = find_parser.add_argument_group(title='Match actions: Change how matched objects are processed')
    find_action_group.add_argument('--printpy', type=str, metavar="PYEXPR",
                                   help='evaluate Python expression PYEXPR in namespace of each match')
    find_action_group.add_argument('--cmd', type=str, metavar="CMD",
                                   help='execute Pob command CMD in namespace of each match')
    find_action_group.add_argument('-l', action='store_true', help='execute "ls -l" on each match')
    find_action_group.add_argument('-x', action='store_true', help='execute "ls -x" on each match')
    find_action_group.add_argument('-e', '--enumerate', action='store_true',
                                   help='enumerate paths matched; to visit with "cd $N"',
                                   default=False)
    find_action_group.add_argument('-q', '--quiet', action='store_true',
                                   help="don't output paths of matched objects",
                                   default=False)

    # meta match criteria
    find_match_options = find_parser.add_argument_group(title='Match options: Change how matches are tested')
    find_match_options.add_argument('-i', '--ignore-case', action='store_true', help='use case-insensitive pattern matching', default=False)
    find_match_options.add_argument('-r', '--regex', action='store_true', help='use regex pattern matching')
    find_match_options.add_argument('-o', '--or', '--any', action='store_true', help="Match objects if ANY of the criteria are satisified")
    find_match_options.add_argument('--noraise', action='store_true', help="ignore CMD errors and MATCHPY exceptions")


    # search algorithm params
    search_logic_options = find_parser.add_argument_group(title='Search logic options: Change how paths are walked')
    search_logic_options.add_argument('-L', '--LIMIT', type=int, metavar='N', help='Stop when N matches found')
    # search_logic_options.add_argument('-uniq', action='store_true', help="search only the first instance of each object that is met (by id)")
    search_logic_options.add_argument('-d', '--maxdepth', type=int, metavar='N',
                                      help=f"Descend no more than N levels below starting dir; default is {PobPrefs.default_maxdepth}")
    search_logic_options.add_argument('--mindepth', type=int, metavar='N',
                                      help=f"Don't report matches less than N levels below starting dir")
    search_logic_options.add_argument('-D', '--DEPTHFIRST', action='store_true', help='search children before siblings')
    search_logic_options.add_argument('--revisit', type=str, choices=['none', 'successes', 'all'], default='successes',
                                      help="Search objects that were already searched? \nDefault is --revisit succcesses")

    pruneset_option = search_logic_options
    pruneset_option.add_argument('--prune', nargs='+',
                                 help='Prune objects from search by abspath, typename or predicate')

    # namespace mapping options
    namespace_mapping_options = find_parser.add_argument_group(title='Mapping options: Change map from Python-objects to Pob-namespaces')
    namespace_mapping_options.add_argument('-a', '--all', action='store_true', help='include objects hidden by "hide" command')
    namespace_mapping_options.add_argument('--map', choices=PobPrefs.map_option_names, help='apply a single temporary map setting')

    # debug flags
    namespace_mapping_options = find_parser.add_argument_group(title='Debug flags')
    find_parser.add_argument('--explain', type=str, help='SUPPRESS')
    # help="(debugging) print debug info walking paths that match wildcard path pattern EXPLAIN ")


    @cmd2.with_argparser(find_parser)
    def do_find(self, args):
        """
        Recursive search for objects with specific characteristics

        Match criteria are pattern matched strings
        Patterns are glob wildcards by default; use -r option for regex

        Valid match criteria:
            - pobshell info functions to apply, and wildcards to test result for a match
                e.g. --name is*  or e.g. --predicates *ismethod*
                Relevant find arguments --name, --cat, --doc, --filepath, --id, --mro, --predicates, --pypath, --signature,
                                        --type, --typename, --value, --path,

            -matchpy with a python expression for 'self' or 'pn' that returns True
                e.g. "len(self)>1000" or "len(list(pn.all_child_paths()))==0"

            All criteria must match, unless the -or option is used in which case any match is enough
            """

        def walk_gen(walk_func, walk_params, max_limit=None):
            while max_limit is None or walk_params['max_depth'] <= max_limit:
                yield from walk_func(**walk_params)
                walk_params['min_depth'] += 1
                walk_params['max_depth'] += 1


        self.recover_contentkey_args(args)

        # set base prune function to match --prune options if given (can be multiple)
        if getattr(args, 'prune', None):
            prune_funcs = []
            for pn in getattr(args, 'prune', ''):
                self.add_prune(pn, prune_funcs, args=args)
            base_prune_func = lambda pn: any(pf(pn) for pf in prune_funcs)
        else:
            base_prune_func = None

        # update the prune function to handle --CODE, --DATA or other pruneset name from user_defs.py
        #   logic is to prune pn's that match --prune spec OR pruneset's prune spec
        prune_postmatch = base_prune_func
        pruneset_map = None

        for pruneset_name in PobPrefs.prunesets.keys():
            if getattr(args, pruneset_name, None):
                if base_prune_func is None:
                    # No --prune option was given, look up the pruneset's prune function
                    prune_postmatch = PobPrefs.prunesets[pruneset_name]
                else:
                    # Combine --prune option with the pruneset's prune function
                    prune_postmatch = lambda pn: base_prune_func(pn) or PobPrefs.prunesets[pruneset_name](pn)
                pruneset_map = PobPrefs.pruneset_maps[pruneset_name]
                break  # only support one pruneset at a time for now

        # stacked_command guarantees to return map to prior setting after code block executes even if exception occurs
        with self.stacked_command(PobPrefs.map_repr()):

            # map preset change must come before prune functions are set

            # set the temporary map(s)
            #   if pruneset has an associated map, apply that first
            #   if user has specified a map, apply that second
            if pruneset_map:
                self.onecmd_plus_hooks(f'''map -q {pruneset_map}''', add_to_history=False)
            if getattr(args, 'map', None) is not None:
                self.onecmd_plus_hooks(f'''map -q {args.map}''', add_to_history=False)

            try:
                if getattr(args, 'path'):
                    start_path = self.normpath(args.path)
                else:
                    start_path = self.curr_path.abspath
                start_node = PobNode(start_path, self.rootpn)
            except (ValueError, dirops.PobMissingMemberException):
                if '*' in args.path:
                    self.perror(f'find: {args.path}: Find does not support wildcard paths')
                else:
                    self.perror(f'find: {args.path}: Invalid path')
                return



            filters_dict = extract_filter_criteria(args, infocmds.INFOFILTERS, for_show=False)
            match_funcs = [func for (pat, func) in filters_dict.values() if func is not None]

            if getattr(args, 'or'):
                match_func = lambda x: any(mf(x) for mf in match_funcs)  # match satisfied if object matches any criteria
            else:
                match_func = lambda x: all(mf(x) for mf in match_funcs)  # match only satisfied if object matches all criteria


            if args.all:  # or not PobPrefs.hide_matched_patterns:
                prune_prematch = None
            else:
                prune_prematch = self._nolist_func

            if args.maxdepth is not None:
                max_depth_absolute = args.maxdepth + start_node.depth()
            else:
                max_depth_absolute = ((PobPrefs.default_maxdepth + start_node.depth()) if PobPrefs.default_maxdepth >= 0
                                      else None)
                # default_maxdepth of -1 indicates no max, in which case set max_depth_absolute to None

            if args.mindepth is not None:
                min_depth_absolute = args.mindepth + start_node.depth()
            else:
                min_depth_absolute = None

            explain_func = None
            if args.explain:
                explain_func = lambda x: fnmatch.fnmatchcase(str(x.abspath), args.explain)

            ns_walk_kwargs = {
                "pob": self,
                "match_func": match_func,
                "prune_prematch": prune_prematch,
                "prune_postmatch": lambda node: prune_postmatch and prune_postmatch(node) and node.abspath != start_path,
                # Don't prune the pobnode we start at
                "find_flags": self.find_flags,
                "feedback_freq": 0 if args.cmd2_statement.get().pipe_to else self.trace_frequency,
                "explain_func": explain_func,
                "revisit_policy": args.revisit,
                "noraise": args.noraise,
            }

            if args.DEPTHFIRST:
                ns_walk_kwargs['min_depth'] = min_depth_absolute
                ns_walk_kwargs['max_depth'] = max_depth_absolute

                walk_chain = start_node.ns_walk(**ns_walk_kwargs)
            else:
                # make a chain of iterators of increasing min_depth and max_depth
                #   it's inefficient because search at depth N repeats a silent search of depths 0 .. N-1
                #   if max_depth_absolute is None, the chain goes on forever
                #   otherwise stops at max_depth_absolute
                ns_walk_kwargs["min_depth"] = min_depth_absolute if min_depth_absolute is not None else 0
                ns_walk_kwargs["max_depth"] = ns_walk_kwargs["min_depth"]

                walk_chain = itertools.chain(walk_gen(start_node.ns_walk, ns_walk_kwargs, max_depth_absolute))


            if args.enumerate:
                self._result_paths = []

            subcmd = args.cmd   # --cmd COMMAND to be executed on each match

            if subcmd and (args.l or args.x):
                self.perror("find: --cmd, --l and --x are mutually exclusive")
                return
            elif args.x:
                subcmd = 'ls -xv .'
            elif args.l:
                subcmd = 'ls -lv .'


            # ========= start walking ==========

            match_count = 0
            for pn in walk_chain:
                self.clean_update_msgs_output()

                if not subcmd:
                    if args.enumerate:
                        self.poutput(boldit(str(match_count)) + ': ', end='')
                        self._result_paths.append(pn.abspath)
                    if not args.quiet:
                        self.poutput(f"{short(pn.abspath)}", end='  ' if args.printpy else '\n')
                    match_count += 1

                if args.printpy:
                    # if the user provided a python expression to eval and printpy for matches, do it now
                    self.poutput(pn.eval_PYEXPR(args.printpy, expecting_eval=True, noraise=args.noraise),
                                 end='  ' if subcmd else '\n')  # cmd results on same line if possible

                if subcmd:
                    # if the user provided a pobshell command to execute for all matches, do it now, reentrantly
                    #   NB don't clobber cdh history with these
                    # stack a command that will cd back to current path (currrent 'working directory')
                    with self.stacked_command(f'''cd {self.curr_path.abspath} --noclobber '''):
                        # 'cd' to the path
                        self.change_curr_path(pn)
                        if args.enumerate and not args.quiet:
                            self.poutput(boldit(str(match_count)) + ': ', end='')
                            self._result_paths.append(pn.abspath)
                        match_count += 1
                        cmds = parse_cmds(subcmd)  # split ";" delimited string of commands

                        # execute --cmd commmands in the namespace of this result path
                        if self.runcmds_plus_hooks(cmds, add_to_history=False, stop_on_keyboard_interrupt=True):
                            return


                if args.LIMIT and match_count >= args.LIMIT :
                    # We found enough matches, stop looking
                    return


                # end of loop enumerating the matched paths
            self.clean_update_msgs_output()



    def clean_update_msgs_output(self):
        # Overwrite updated messages (e.g. track_find)  with spaces, so the new output we want to show isn't garbled by it
        if self.trace_frequency:
            self.pfeedback(" " * (PobPrefs.width - 1), end="\r")


    # ==========================================================================================
    # ## formatting UTILITIES  ============================================================================
    # ==========================================================================================


    def output_pobshell_banner(self):
        if not self.quiet:
            self.poutput("\nWelcome to Pobshell - type '" + boldit("help") + "' for commands, '"
                         + boldit("quit") + "' to exit ")
            if PobPrefs.DEBUG:
                self.poutput(datetime.now())


    def columnize(self, str_list: Optional[List[str]], display_width: int = 80) -> None:
        """Display a list of single-line strings as a compact set of columns.
        Override of cmd2's columnize to fix bug with columnize initialisation
        from colwidths = [0]
        to colwidths = [None]
        Override of cmd's print_topics() to handle strings with ANSI style sequences and wide characters

        Each column is only as wide as necessary.
        Columns are separated by two spaces (one was not legible enough).
        """
        if not str_list:
            self.poutput("<empty>")
            return

        nonstrings = [i for i in range(len(str_list)) if not isinstance(str_list[i], str)]
        if nonstrings:
            raise TypeError(f"str_list[i] not a string for i in {nonstrings}")
        size = len(str_list)
        if size == 1:
            self.poutput(str_list[0])
            return
        # Try every row count from 1 upwards
        for nrows in range(1, len(str_list)):
            ncols = (size + nrows - 1) // nrows
            colwidths = []
            totwidth = -2
            for col in range(ncols):
                colwidth = 0
                for row in range(nrows):
                    i = row + nrows * col
                    if i >= size:
                        break
                    x = str_list[i]
                    colwidth = max(colwidth, ansi.style_aware_wcswidth(x))
                colwidths.append(colwidth)
                totwidth += colwidth + 2
                if totwidth > display_width:
                    break
            if totwidth <= display_width:
                break
        else:
            nrows = len(str_list)
            ncols = 1
            colwidths = [None]
        for row in range(nrows):
            texts = []
            for col in range(ncols):
                i = row + nrows * col
                if i >= size:
                    x = ""
                else:
                    x = str_list[i]
                texts.append(x)
            while texts and not texts[-1]:
                del texts[-1]
            for col in range(len(texts)):
                texts[col] = utils.align_left(texts[col], width=colwidths[col])
            self.poutput("  ".join(texts))


    cmd2.categorize(
        (do_cd, do_pwd, do_cdh),
        CMD_CAT_PATH_MANIPULATION)

    cmd2.categorize(
        (do_tree, do_find),
        CMD_CAT_LIST_DIR)

    cmd2.categorize(
        (do_hide, do_show, do_map, do_mount, do_unmount),
        CMD_CAT_MAP)

    cmd2.categorize(
        (do_eval, do_rooteval, do_ipy, do_py),
        CMD_CAT_PYTHON)

    cmd2.categorize(
        (do_quit, do_newline, do_comment, do_die, do_man,
         cmd2.cmd2.Cmd.do_help, cmd2.cmd2.Cmd.do_set),
        CMD_CAT_UTILS)

    cmd2.categorize(
        (do_shell, cmd2.cmd2.Cmd.do_alias, cmd2.cmd2.Cmd.do_edit, cmd2.cmd2.Cmd.do_history, cmd2.cmd2.Cmd.do_macro,
         cmd2.cmd2.Cmd.do_run_pyscript, cmd2.cmd2.Cmd.do_run_script, cmd2.cmd2.Cmd.do_shortcuts),
        CMD_CAT_SCRIPTING)

    cmd2.categorize(
        (do_killsession, do_test, do_addtest, do_break, do_introspect, do_reset, ),
        CMD_CAT_POBSHELL_TESTING)



def ansi_aware_write_jupyter(fileobj: IO[str], msg: str) -> None:
    """
    Write a string to a fileobject and strip its ANSI style sequences if required by allow_style setting
    Monkey patch for cmd2.ansi.ansi_aware_write which does not strip ANSI if we're running in jupyter

    :param fileobj: the file object being written to
    :param msg: the string being written
    """

    ansi = cmd2.ansi
    if ansi.allow_style == ansi.AllowStyle.NEVER or (ansi.allow_style == ansi.AllowStyle.TERMINAL
                                                    and not (fileobj.isatty() or common.UNRELIABLE_WIDTH_RESPONSE)):
        msg = ansi.strip_style(msg)
    fileobj.write(msg)
