import inspect

import shutil
import os

import string
import json

import sys
from pprint import saferepr

from contextlib import redirect_stderr, contextmanager
import io

from typing import Union
from cmd2 import Fg, ansi

from . import dirops

# TODO: make this a path a pobshell.shell() and pobshell.pob() parameter

DEFAULT_SETTINGS_FILE = os.path.split(__file__)[0] + "/user_defs.py"
MAN_FOLDER = os.path.split(__file__)[0] + '/manpages'  # or an absolute path if you like

# These specify the names added to python namespace when creating py or ipy shell,
#   or evaluating a user python expression with PN.eval_PYEXPR
# They allow user code to refer to object at a path and it corresponding pobnode
SELF_NAME = 'self'
POBNODE_NAME = 'pn'

RAW_LABEL = "[TRUNCATED]"
LABEL_LEN = len(RAW_LABEL)
STYLED_LABEL = ansi.style(RAW_LABEL, underline=True)


def short(txt: str, max_width=None) -> str:
    """Truncate string to screen width by eliding centre of string """
    if max_width is None:
        max_width = PobPrefs.path_width
        # max_width = .
    if max_width >= len(txt):
        return txt

    left_count = (max_width - LABEL_LEN) // 2
    right_count = max_width - LABEL_LEN - left_count

    return txt[:left_count] + STYLED_LABEL + txt[-right_count:]


def fmt_update_msg(txt: str) -> str:
    """Truncate arg to fit 1-line width, pad with spaces to overwrite earlier messages, & append CR """
    msg = short(txt, max_width=PobPrefs.width-10)  # truncate message below screen width
    return msg + " " * max(0, PobPrefs.width - len(msg)) + "\r"    # overwrite earlier messages


def xtra_safe_repr(obj):
    """Return saferepr for obj, but catch exceptions and fall back to id(obj)+ <Exception text>"""
    # Some objects return an exception if you repr them.  Looking at you, openai
    try:
        return saferepr(obj)
    except KeyboardInterrupt:
        raise
    except Exception as e:
        return f"Broken repr Exception: {id(obj)}::{str(e)}>"


def context_is_ide_or_notebook():
    try:
        ipy_str = str(type(get_ipython()))
        if 'zmqshell' in ipy_str:
            return True
        if os.environ['PYCHARM_HOSTED']==1:
            return True
    except:
        pass
    return False


def valid_contentkey_delimiter_char(delim_char: str):
    """Validate single char for 'contentkey_delimiter' settable, to delimit stringified Python objects used as namespace keys"""
    disallowed_chars = r"""!"#$%&'()*+,-./:<=>?@[\]^{|}~_§""" + string.ascii_letters + string.digits + string.whitespace
    if delim_char in disallowed_chars or len(delim_char) != 1:
        raise ValueError('''Content key delimiter must be a single character: A backtick "`" or a non-ascii symbol, e.g. "°" or "±"''')

    return delim_char



UNRELIABLE_WIDTH_RESPONSE = context_is_ide_or_notebook()

class Nonesuch(Exception):  # Just for debugging, never caught since never raised
    pass


# Placeholder object which may be returned when PobNode's info functions trap an Exception
#   (if PobNode.prettify_infos is true, otherwise '' is returned)
class NoSuchInfo(Exception):
    def __init__(self, exception=''):
        self._exception = exception if isinstance(exception, Exception) else None
        self._description = str(exception)

    def __str__(self):
        if self._description:
            return "NoSuchInfo('"+self._description+"')"
        else:
            return 'NoSuchInfo'


class ObjNone:
    """ A sentinel singleton representing the lack of an object in a pob datastructure
        - a substitute for None which is a valid object found at some paths
        Use the class itself, no need to instantiate
    """
    pass


class MissingInfoOptions:
    skip_item = "skip"
    empty_string = "blank"
    exception_string = "message"

    valid_values = "  ['skip': omit member & info \n   'blank': blank info \n   'message': report error message]"
    choices = [skip_item, empty_string, exception_string]



class PobPrefsClass:  # Singleton container object for pobshell preferences

    auto_import = False      # by default don't auto-import subpackes or modules as namespace entries
    recursive_find_protection = 1
    contents_limit = 2000   # Maximum number of items to return for a collection. Set it to -1 for no maximum (but don't)
    default_maxdepth = 4    # Set it to -1 for no default max depth

    missing = MissingInfoOptions.skip_item

    #   when prettify_infos is true, info-func output has syntax highlighting of code & signature strings,
    #       pretty printing of value strings, cleaning of doc strings, and colouring of pydoc output
    #       these are temporarily turned off when evaluating --cat --signature --matchpy, to prevent
    #       ansi codes from breaking pattern matching of output.  And all styling is turned off when
    #       output is sent to an OS pipe, e.g. for grep
    #       prettify_infos not a user setting, but user can turn off all colouring with
    #           set allow_style Never
    prettify_infos = True

    def __init__(self):

        self.DEBUG = False  # True when debugging pobshell or creating tests

        # attributes that implement PV settings  ------------
        #   see Pobiverse __init__ for descriptions/help text

        # TODO: Consolidate these instance attributes with class attributes above

        # NB Need consistent width setting for tests, or output won't match
        # DEBUG may be overridden in init_options; width and path_width will be updated if necessary
        self.width = 120 if self.DEBUG else shutil.get_terminal_size().columns
        self.path_width = self.width * 3 // 2  # this value is also updated in load_settings

        self.column_width = 24
        self.null_separator = False
        self.linenumbers = False
        self.flatten_multiline = False

        self.theme = 'dark'
        self._global_ns = '/'
        self.simple_cat_and_doc = True

        self._contentkey_delimiter = "`"

        # The settings below are updated from user_defs.py by a Pobiverse (PV) call to PobPrefs.load_settings
        #   when it knows the path during PV.__init__
        self.user_namespace = {}
        self.contentkey_delimiter = "\u2063"
        self.lsx_cmds = None
        self.lsxv_cmds = None
        self.lsl_func = None
        self.lsl_style_list = None
        self.pruneset_maps = None
        self.prunesets = None
        self.themes = None

        self.available_filters = None

        # map settings

        self.map_option_names = ('attributes', 'contents', 'everything', 'dynamic', 'static',
                                 'mro', 'local', 'variables', 'frameattrs')
        self.static = False  # Default is dynamic retrieval of object attributes with getattr()
        self.mro = True   # Default of .mro True will retrieve attributes for a class from its mro hierarchy
                          # and for an instance, from its class and the class's mro hierarchy
        self._contents = False   # True -> contents of collections also mapped
        self.attributes = True
        self.simpleframes = True  # True -> map globals & vars ; False -> map raw Frame object attributes


    def init_options(self, options_dict):
        """
        Set PobPrefs attributes passed in Pobmain **kwargs

        Currently only handles DEBUG parameter
        Args:
            options_dict: {'DEBUG': required value for PobPrefs.DEBUG}
        Returns:
            None
        """
        for k, v in options_dict.items():
            setattr(self, k, v)
        #  update attributes that depend on other attributes
        #  TODO make this a method
        if 'width' not in options_dict:
            self.width = 120 if self.DEBUG else shutil.get_terminal_size().columns
        if 'path_width' not in options_dict:
            self.path_width = self.width * 3 // 2  # this value is also updated in load_settings


    def map_description(self):   # TODO 24 Mar 2025 -- update this for onlycontents setting
        """return str of current map settings"""

        return (f"  members: \'{self.member_desc}\'"
                f"  binding: \'{'static' if self.static else 'dynamic'}\'"
                f"  resolution: \'{'mro' if self.mro else 'local'}\'"
                f"  frames: \'{'variables' if self.simpleframes else 'frameattrs'}\'"
                )


    def map_repr(self):   # TODO 24 Mar 2025 -- update this for onlycontents setting
        """return str of current map settings as a map command"""

        # NB uses map -q option so no feedback is sent to the user
        #   it's used to reset a map after a temporary setting, e.g. "ls --map local"
        return (f"map -q {self.member_desc}"
                f"  {'static' if self.static else 'dynamic'}"
                f"  {'mro' if self.mro else 'local'}"
                f"  {'variables' if self.simpleframes else 'frameattrs'} ")


    @property
    def member_desc(self) -> str:
        """Return description string for one of the map parameters"""
        if self.contents:
            if self.attributes:
                return 'everything'
            else:
                return 'contents'
        else:
            return 'attributes'


    def load_settings(self, path=None):
        if not path:
            path = DEFAULT_SETTINGS_FILE
        try:
            with open(path, "r") as f:
                code = f.read()
                exec(code, self.user_namespace)
        except OSError as e:
            print(f"Unable to read settings file user_defs.py")
            raise

        for k, v in self.user_namespace.items():
            if k == 'contentkey_delimiter':
                assert valid_contentkey_delimiter_char(v)
                self._contentkey_delimiter = v
            elif k == 'lsx_cmds':
                self.lsx_cmds = v
                self.lsxv_cmds = [c+'v' for c in v]  # append 'verbose' option to each command
            elif k in {'lsl_func', 'lsl_style_list', 'pruneset_maps', 'prunesets',
                       'themes', 'available_filters'}:
                setattr(self, k,  v)




    @property
    def global_ns(self):
        return self._global_ns

    @global_ns.setter
    def global_ns(self, new_value: str):
        # currently only supports none and /
        new_value = new_value.strip()
        if new_value.lower() == "none":
            self._global_ns = None
        elif new_value.startswith('/'):
            self._global_ns = new_value
        else:
            self._global_ns = new_value  # "user"


    @property
    def contents(self):
        return self._contents

    @contents.setter
    def contents(self, new_value: bool):
        # if contents is set True, assign contentkey delimiter from json file setting
        # if contents is set False, assign key delimiter to Uncommon Mark, an invisible Separator,
        #   (unlikely to be noticed or searched for).
        # This is to avoid any backtick processing whatsoever when processing PV's command arguments
        self._contents = new_value
        if new_value:
            self.contentkey_delimiter = self._contentkey_delimiter
        else:
            self.contentkey_delimiter = "\u2063"


    @property
    def current_theme(self):
        return self.themes[self.theme]

    @property
    def lsl_styles(self):
        return [{'fg': Fg[self.current_theme[style_name]]} if style_name else {} for style_name in
                  self.lsl_style_list]


# Instantiate our singleton PobPrefs settings object
#    Though it has expanded its role rather a lot.
#    TODO Needs Refactoring
PobPrefs = PobPrefsClass()


@contextmanager
def temporary_setting(attr_name, temp_value, preference_container=PobPrefs):
    """Temporarily set an attribute on PobPrefs for the duration of the context manager."""
    assert hasattr(preference_container, attr_name)
    old_value = getattr(preference_container, attr_name)
    setattr(preference_container, attr_name, temp_value)
    try:
        yield
    finally:
        setattr(preference_container, attr_name, old_value)

