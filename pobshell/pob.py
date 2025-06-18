import importlib
import sys

from .pobmain import Pobiverse, POB_HALT, POB_CONTINUE
from . import pobmain

import inspect

HALT_REQUESTED = False
FIRST_RUN = True

def reload_pobshell_modules():
    """Reload Pobshell modules in an attempt to clean up global state."""

    # It's a big job to refactor Pobshell, PobPrefs and infocmds to remove global state
    #   This is the best I can manage for now, and it seems to be working ok
    # RESET Pobshell modules and restart the cmdloop

    global Pobiverse, POB_HALT, POB_CONTINUE
    for name, module in list(sys.modules.items()):
        if name.startswith("pobshell") and name != "pobshell.pob":  # Reload all except this module
            importlib.reload(module)


def shell(root: object = None, map_init: str | None = None, cmd: str | None = None, **kwargs):
    """ Initialise pobshell and start command loop

    Supports this kind of use of Pobshell:
      import pobshell
      pobshell.shell()
      / ▶ ls -l foo

    Args:
        root: Object with which to populate root
              If no root object provided, use calling frame, but exclude Pobshell objects
        map_init: String containing initial map settings
        cmd: ;-delimited string with Pobshell commands to run at startup

    Returns: None

    """


    global HALT_REQUESTED, FIRST_RUN

    try:
        # HALT_REQUESTED is set by die command (do_die) inside Pobiverse in case of repeated invocations of shell.
        if HALT_REQUESTED:
            return

        if not FIRST_RUN:
            reload_pobshell_modules()  # try for clean app state
        else:
            FIRST_RUN = False

        retval = pobmain.POB_CONTINUE  # cmdloop returns CONTINUE to re-init Pobiverse
        while retval == pobmain.POB_CONTINUE:

            if root:
                pob = Pobiverse(root=root, map_init=map_init, interactive=True, **kwargs)
            else:
                pob = Pobiverse(root=inspect.currentframe().f_back, map_init=map_init, interactive=True, **kwargs)
            if cmd:
                pob.cmd(cmd)
            retval = pob.cmdloop()

            if retval == pobmain.POB_HALT:
                HALT_REQUESTED = True
                return

            if retval == pobmain.POB_CONTINUE:
                # It's a big job to refactor Pobshell, PobPrefs and infocmds to remove global state
                #   This is the best I can manage for now, and it seems to be working ok
                # RESET Pobshell modules and restart the cmdloop
                if 'pob' in locals() and hasattr(pob, 'clear_refs'):
                    pob.clear_refs()
                reload_pobshell_modules()
    finally:
        del root    # make sure to del any frame reference


def pob(root: object = None, map_init: str | None = None, cmd: str | None = None, **kwargs) -> Pobiverse:
    """ Initialise pobshell and return a handle to Pobiverse object

    Supports this kind of use of Pobshell:
      import pobshell
      POB = pobshell.pob(root=obj, persistent_history_file=None)
      POB.onecmd_plus_hooks('ls -l foo')
      ...
      POB.clear_refs()

    IMPORTANT: When using pobshell.pob() interactively, you must call the returned object's clear_refs() method
      or execute the quit command when you're done.  Otherwise, Pobiverse may retain a reference to the calling
      frame, creating a circular reference that can lead to a memory leak

    Args:
        root: Object with which to populate root
              If no root provided, use calling frame, but exclude Pobshell objects
        map_init: String containing initial map settings
        cmd: ;-delimited string with Pobshell commands to run at startup

    Returns:  Instance of Pobiverse object initialized as per arguments provided
    """
    # TODO Should this be using cmd2's py_bridge?

    global HALT_REQUESTED, FIRST_RUN

    try:
        if HALT_REQUESTED:  # invoked by die command (do_die) inside Pobiverse in case of repeated invocations of shell.
            return

        if not FIRST_RUN:
            reload_pobshell_modules()  # try for clean app state
        else:
            FIRST_RUN = False

        if root:
            PV = Pobiverse(root=root, map_init=map_init, interactive=False, **kwargs)
        else:
            PV = Pobiverse(root=inspect.currentframe().f_back, map_init=map_init, interactive=False, **kwargs)
        if cmd:
            PV.cmd(cmd)

        return PV

    finally:
        del root   # Superstitiously making sure to del any frame reference retained in this function's namespace



def reset():
    global HALT_REQUESTED
    HALT_REQUESTED = False

