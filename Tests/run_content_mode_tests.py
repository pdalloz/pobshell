import sys
import unittest

# import sympy
# conda install sympy=1.9
import re

from contextlib import (
    redirect_stderr,
    redirect_stdout,
)

from pobshell import strpath, pobmain

from cmd2.utils import (
    StdSim,
)

import sample_dynamic_test_code

# assert sympy.__version__ == '1.9'  # some tests rely on a specific version of sympy


def normalize_lines(block):
    """Normalize a block of text to a list of lines

    Strip newlines from the very beginning and very end  Then split into separate lines and strip trailing whitespace
    from each line.
    """
    assert isinstance(block, str)
    block = block.strip()
    return [line.rstrip() for line in block.splitlines()]


def normalize_cols(block):
    """Normalize a block of text from lines and colummns to a list

    Strip newlines from the very beginning and very end, and split on whitespace
    """
    assert isinstance(block, str)
    block = block.strip()
    return [item for item in re.split(r'\s+', block)]


def run_cmd(app, cmd, errs=False, norm=True):
    """Clear out and err StdSim buffers, run the command, and return out and err"""
    saved_sysout = sys.stdout
    sys.stdout = app.stdout

    # This will be used to capture app.stdout and sys.stdout
    copy_cmd_stdout = StdSim(app.stdout)

    # This will be used to capture sys.stderr
    copy_stderr = StdSim(sys.stderr)

    try:
        app.stdout = copy_cmd_stdout
        with redirect_stdout(copy_cmd_stdout):
            with redirect_stderr(copy_stderr):
                app.onecmd_plus_hooks(cmd)
    finally:
        app.stdout = copy_cmd_stdout.inner_stream
        sys.stdout = saved_sysout

    if errs:
        return normalize_lines(copy_stderr.getvalue()) if norm else copy_stderr.getvalue()
    return normalize_lines(copy_cmd_stdout.getvalue()) if norm else copy_cmd_stdout.getvalue()


class test_PySh(unittest.TestCase):

    def test_parentpath(self):
        run_cmd(PApp, 'cd /')

        self.assertEqual(strpath.dirname('/'), '/')
        self.assertEqual(strpath.dirname('/dynamic_test_code'), '/')
        self.assertEqual(strpath.dirname('/nonesuch'), '/')
        self.assertEqual(strpath.dirname('/dynamic_test_code/A'), '/dynamic_test_code')

        run_cmd(PApp, 'cd dynamic_test_code')
        self.assertEqual(strpath.dirname(PApp.normpath('.')), '/')

        # cd into a list object
        run_cmd(PApp, 'cd /dynamic_test_code/long_list')

        run_cmd(PApp, 'cd /')


    def test_abspath(self):
        run_cmd(PApp, 'cd /')
        self.assertEqual(PApp.normpath('/'), '/')
        self.assertEqual(PApp.normpath('/dynamic_test_code'), '/dynamic_test_code')
        self.assertEqual(PApp.normpath('dynamic_test_code'), '/dynamic_test_code')
        self.assertEqual(PApp.normpath('dynamic_test_code/A'), '/dynamic_test_code/A')

        self.assertEqual(PApp.normpath('/dynamic_test_code/..'), '/')
        self.assertEqual(PApp.normpath('..'), '/')  # parent of root is root

        self.assertEqual(PApp.normpath('/dynamic_test_code/A/..'), '/dynamic_test_code')
        self.assertEqual(PApp.normpath('/dynamic_test_code/A/../'), '/dynamic_test_code')
        # /dynamic_test_code/FrenchDeck/suits/`3`
        # /dynamic_test_code/FrenchDeck/../A
        self.assertEqual(PApp.normpath('/dynamic_test_code/FrenchDeck/../A'), '/dynamic_test_code/A')

        self.assertEqual(PApp.normpath('/dynamic_test_code/FrenchDeck'), '/dynamic_test_code/FrenchDeck')

        run_cmd(PApp, 'cd /dynamic_test_code')
        self.assertEqual(PApp.normpath('../dynamic_test_code'), '/dynamic_test_code')

        run_cmd(PApp, 'cd /../dynamic_test_code/A')
        self.assertEqual(PApp.normpath('../..'), '/')

        # /dynamic_test_code/FrenchDeck/suits/`3`
        run_cmd(PApp, 'cd  /dynamic_test_code/FrenchDeck/suits')
        self.assertEqual(PApp.normpath('../../..'), '/')
        self.assertEqual(PApp.normpath('../..'), '/dynamic_test_code')

        run_cmd(PApp, 'cd /')

    def test_cd(self):
        run_cmd(PApp, 'cd /')
        run_cmd(PApp, 'cd dynamic_test_code/FrenchDeck')
        self.assertEqual(PApp.curr_path.abspath, '/dynamic_test_code/FrenchDeck')
        run_cmd(PApp, 'cd /')

    def test_zzzfind(self):
        # add zzz's to name so its run last
        run_cmd(PApp, 'cd /dynamic_test_code')

        # check that -winner works
        run_cmd(PApp, 'set quiet false')
        # get results from stdout
        # find /dynamic_test_code/FrenchDeck/ -name `3` -depthfirst -winner 'pobns.depth'
        run_cmd(PApp, "set track_find false")
        out = run_cmd(PApp, "find /dynamic_test_code/FrenchDeck/ -name `3` -depthfirst -winner 'pobns.depth'", norm=True)
        # get Leader updates from stderr (since quiet is false)
        outErr = run_cmd(PApp, """find /dynamic_test_code/FrenchDeck/ -name `3` -depthfirst -winner 'pobns.depth'""",
                         norm=True, errs=True)
        # check results
        # />find /dynamic_test_code/FrenchDeck/ -name `3` -depthfirst -winner "self.depth"
        # [Leader: <ObjPath /dynamic_test_code/FrenchDeck/ranks/`3`  5>]
        # [Leader: <ObjPath /dynamic_test_code/FrenchDeck/suits/`0`/`3`  d>]
        # /dynamic_test_code/FrenchDeck/suits/`0`/`3`
        # /dynamic_test_code/FrenchDeck/suits/`1`/`3`
        # /dynamic_test_code/FrenchDeck/suits/`2`/`3`
        # /dynamic_test_code/FrenchDeck/suits/`3`/`3`
        self.assertEqual(len(out), 4)
        self.assertTrue(all(a.count('/') == 5 for a in out))  # check the four winners have depth of 4
        # check Leader updates
        self.assertEqual(len(outErr), 2)
        self.assertTrue(all(a.startswith('[Leader') for a in outErr))  # check for the two Leader updates

        # check that set quiet true suppresses 'Leader' updates
        run_cmd(PApp, 'set quiet true')
        out = run_cmd(PApp, "find /dynamic_test_code/FrenchDeck/ -name `3` -depthfirst -winner 'pobns.depth'", norm=True,
                      errs=True)
        self.assertEqual(len(out), 0)

        # check that limit 1 works, and that wildcard name matching works

        out = run_cmd(PApp, "find /dynamic_test_code/FrenchDeck/ -name `1*` -depthfirst -winner 'len(self.name)' -limit 1", norm=True)
        self.assertEqual(out, ['/dynamic_test_code/FrenchDeck/ranks/`10`'])

        # check that find -a searches within hidden namepaces
        out = run_cmd(PApp, "find -a -maxdepth 4 . -name __c*_ -limit 2 -depthfirst", norm=True)
        self.assertEqual(out[-1], "/dynamic_test_code/A/__class__/__base__/__class__")

        # Test recursive find
        # check that limit works and check quoted python expressions without an equals sign
        out = run_cmd(PApp, "find /dynamic_test_code -name suit -depthfirst -print 'pobns.abspath' -limit 4 -maxdepth 6", norm=True)
        # /dynamic_test_code/Card/suit
        # /dynamic_test_code/beer_card/suit
        # /dynamic_test_code/deck/`0`/suit
        # /dynamic_test_code/deck/`1`/suit
        self.assertEqual(len([o for o in out if o != "VerboseAttribute: Getting the attribute value"]), 4)

        out = run_cmd(PApp, "find /dynamic_test_code/FrenchDeck/ -name `3` -depthfirst -print 'pobns.abspath'", norm=True)
        sample_expected_results = ["/dynamic_test_code/FrenchDeck/ranks/`3`",
                                   "/dynamic_test_code/FrenchDeck/suits/`0`/`3`",
                                   "/dynamic_test_code/FrenchDeck/suits/`1`/`3`",
                                   "/dynamic_test_code/FrenchDeck/suits/`2`/`3`",
                                   "/dynamic_test_code/FrenchDeck/suits/`3`",
                                   "/dynamic_test_code/FrenchDeck/suits/`3`/`3`"]

        for r in sample_expected_results:
            self.assertIn(r, out)

        # check number of results
        self.assertEqual(len(out), 6)  # NB running in terminal gives different result count due to
        #     paths beginning /sympy/testing/runtests/pdoctest/unittest/...
        #     Those paths don't show in results here.  I assume its a unittest thing

    def test_ls(self):
        run_cmd(PApp, 'cd /dynamic_test_code')

        # check ls -a contents matches dir()
        out = normalize_cols(run_cmd(PApp, 'ls -1a', norm=False))
        self.assertEqual(out, dir(dynamic_test_code))

        out = normalize_cols(run_cmd(PApp, 'ls -a', norm=False))
        self.assertEqual(sorted(out), dir(dynamic_test_code))

        # ls should work with . as argument
        out = run_cmd(PApp, 'ls .')
        self.assertEqual(out, ['dynamic_test_code'])

        # ls should match a provided glob pattern
        out = normalize_cols(run_cmd(PApp, 'ls my*', norm=False))
        self.assertEqual(len(out), 2)

        assert PApp._hide_prefixes == ['_']
        # list non hidden
        out = normalize_cols(run_cmd(PApp, 'ls', norm=False))
        self.assertEqual(len(out), 18)
        # list hidden
        out = normalize_cols(run_cmd(PApp, 'ls -1 _* | grep -v _pydev', norm=False))
        self.assertEqual(len(out), 8)
        # list all
        out = normalize_cols(run_cmd(PApp, 'ls -1 *', norm=False))
        self.assertEqual(len([o for o in out if not o.startswith("_pydev_stop_at_break")]), 30)  # 31, of which 1 is  '_pydev_stop_at_break' and 8 are dunders = 22

        out = normalize_cols(run_cmd(PApp, 'ls *ong*', norm=False))
        self.assertEqual(out, ['long_list'])

        # ls with arg not found should show a perror, not raise an exception
        run_cmd(PApp, 'cd /')
        out = run_cmd(PApp, 'ls Nonesuch*/*', errs=True, norm=False)
        self.assertTrue('No such path' in out)

        # ls with arg not found should show a perror, not raise an exception
        out = run_cmd(PApp, 'ls dynamic_test_code/Nonesuch', errs=True, norm=False)
        self.assertTrue('No such path' in out)

        # ls with arg not found should show a perror, not raise an exception
        out = run_cmd(PApp, 'ls Nonesuch/Nonesuch', errs=True, norm=False)
        self.assertTrue('No such path' in out)

        # ls with arg not found should show a perror, not raise an exception
        out = run_cmd(PApp, 'ls Nonesuch/', errs=True, norm=False)
        self.assertTrue('No such path' in out)

        # ls with arg not found should show a perror, not raise an exception
        out = run_cmd(PApp, 'ls /Nonesuch', errs=True, norm=False)
        self.assertTrue('No such path' in out)

        out = run_cmd(PApp, 'ls -x /dynamic_test_code/Card', norm=True)
        self.assertTrue(any("doc                    Card(rank, suit)" in o for o in out))

        # validate ls -x output
        run_cmd(PApp, 'cd /dynamic_test_code/Card')

        run_cmd(PApp, 'set missing empty_string')
        # rank                       _tuplegetter(0, 'Alias for field number 0')  <class '_collections._tuplegetter'>
        #     type                   <class '_collections._tuplegetter'>
        #     signature
        #     predicates             [isdatadescriptor]
        #     doc                    Alias for field number 0
        # suit                       _tuplegetter(1, 'Alias for field number 1')  <class '_collections._tuplegetter'>
        #     type                   <class '_collections._tuplegetter'>
        #     signature
        #     predicates             [isdatadescriptor]
        #     doc                    Alias for field number 1
        out = run_cmd(PApp, 'ls -x')
        self.assertEqual(len(out), 10)

        run_cmd(PApp, 'set missing suppress_line')
        out = run_cmd(PApp, 'ls -x')
        self.assertEqual(len(out), 8)
        # /dynamic_test_code/Card>set missing suppress_line
        # missing - was: 'exception_string'
        # now: 'suppress_line'
        # /dynamic_test_code/Card>ls -x
        # rank                       _tuplegetter(0, 'Alias for field number 0')  <class '_collections._tuplegetter'>
        #     type                   <class '_collections._tuplegetter'>
        #     predicates             [isdatadescriptor]
        #     doc                    Alias for field number 0
        # suit                       _tuplegetter(1, 'Alias for field number 1')  <class '_collections._tuplegetter'>
        #     type                   <class '_collections._tuplegetter'>
        #     predicates             [isdatadescriptor]
        #     doc                    Alias for field number 1

        run_cmd(PApp, 'set missing exception_string')
        # /dynamic_test_code/Card>set missing exception_string
        # missing - was: 'suppress_line'
        # now: 'exception_string'
        # /dynamic_test_code/Card>ls -x
        # rank                       _tuplegetter(0, 'Alias for field number 0')  <class '_collections._tuplegetter'>
        #     type                   <class '_collections._tuplegetter'>
        #     signature              Exception: TypeError("_tuplegetter(0, 'Alias for field number 0') is not a callable object")
        #     predicates             [isdatadescriptor]
        #     doc                    Alias for field number 0
        # suit                       _tuplegetter(1, 'Alias for field number 1')  <class '_collections._tuplegetter'>
        #     type                   <class '_collections._tuplegetter'>
        #     signature              Exception: TypeError("_tuplegetter(1, 'Alias for field number 1') is not a callable object")
        #     predicates             [isdatadescriptor]
        #     doc                    Alias for field number 1
        out = run_cmd(PApp, 'ls -x')
        out2 = [a for a in out if 'Exception' in a]
        self.assertEqual(len(out), 10)
        self.assertEqual(len(out2), 2)

        run_cmd(PApp, 'set missing suppress_line')


    def test_settables(self):
        # check that col 1 is 25 chars for short names
        run_cmd(PApp, 'set ll_col1_width 25')
        out = run_cmd(PApp, 'ls -l /dynamic_test_code/A', norm=False)
        self.assertTrue(out.startswith("A                          <class 'dynamic_test_code.A'>"))

        # check that col 1 is as long as necessary for long names, and adds 2 spaces before rest of entry
        out = run_cmd(PApp, """ls -l /dynamic_test_code/my_global_dict/`("They'd eaten every one.", 64)`""", norm=False)
        self.assertTrue(out.startswith("""`("They'd eaten every one.", 64)`  "The time has come"""))

        # check that col 1 picks up user setting when default width is changed
        # And demonstrate use of glob pattern * inside a backticked key
        run_cmd(PApp, 'set ll_col1_width 40')
        out = run_cmd(PApp, """ls -l /dynamic_test_code/my_global_dict/`("They'd eaten every *.", 64)`""", norm=False)
        self.assertTrue(out.startswith("""`("They'd eaten every one.", 64)`         "The time has come,' the Walrus said"""))

        run_cmd(PApp, 'set ll_col1_width 25')


    def test_info_cmds(self):
        run_cmd(PApp, 'cd /dynamic_test_code')

        run_cmd(PApp, 'set missing suppress_line')

        # doc with a pattern is should only doc the names in the namespace that match the pattern
        out = run_cmd(PApp, 'doc -1 *ard')
        self.assertEqual(len(out), 2)
        self.assertTrue(all([d.endswith('Card(rank, suit)') for d in out]))  # each doc includes the word 'the'

        # test signature works with * and returns correct number of results, also test piping to shell
        out = run_cmd(PApp, 'signature * | grep -v _pydev | wc -l')
        # /dynamic_test_code>signature *
        # A                          ()
        # Card                       (rank, suit)
        # Foo                        ()
        # FrenchDeck                 ()
        # Ten                        ()
        # VerboseAttribute           ()
        # do_stuff                   ()
        # function1                  (my_param: str)
        # main                       ()
        # randint                    (a, b)
        self.assertEqual(out, ['10'])

        # run_cmd(PApp, 'cd /sympy/And')
        run_cmd(PApp, 'set missing suppress_line')
        out = run_cmd(PApp, 'cat -1 ')
        # /dynamic_test_code>cat -1
        # A                                         class A:
        # Foo                                       class Foo:
        # FrenchDeck                                class FrenchDeck:
        # Ten                                       class Ten:
        # VerboseAttribute                          class VerboseAttribute:
        # collections                               '''This module implements specialized container datatypes providing
        # os                                        r"""OS routines for NT or Posix depending on what system we're on.
        # pathlib                                   import fnmatch
        self.assertEqual(len(out), 8)
        out = run_cmd(PApp, 'doc -1 ')
        # /dynamic_test_code>doc -1
        # Card                                      Card(rank, suit)
        # beer_card                                 Card(rank, suit)
        # collections                               This module implements specialized container datatypes providing
        # os                                        OS routines for NT or Posix depending on what system we're on.
        self.assertEqual(len(out), 4)

        run_cmd(PApp, 'set missing empty_string')
        # /dynamic_test_code>set missing empty_string
        # missing - was: 'suppress_line'
        # now: 'empty_string'
        # /dynamic_test_code>cat -1
        # A                          class A:
        # Card
        # Foo                        class Foo:
        # FrenchDeck                 class FrenchDeck:
        # Ten                        class Ten:
        # VerboseAttribute           class VerboseAttribute:
        # a
        # beer_card
        # collections                '''This module implements specialized container datatypes providing
        # deck
        # long_list
        # my_global_dict
        # my_global_str
        # os                         r"""OS routines for NT or Posix depending on what system we're on.
        # pathlib                    import fnmatch
        # rien_de_rien
        # short_list
        # the_walrus_and_the_carpenter_were_walking_close_at_hand
        out = run_cmd(PApp, 'cat -1 ')
        out2 = [a for a in out if 'Exception' in a]
        self.assertEqual(len(out), 18)
        self.assertEqual(len(out2), 0)

        # Adding an asterisk pattern matches hidden objects too
        out = run_cmd(PApp, 'doc -1 *')
        # A
        # Card                       Card(rank, suit)
        # Foo
        # FrenchDeck
        # Ten
        # VerboseAttribute
        # __builtins__
        # __cached__
        # __doc__
        # __file__
        # __loader__                 Concrete implementation of SourceLoader using the file system.
        # __name__
        # __package__
        # __spec__                   The specification for a module, used for loading.
        # a
        # beer_card                  Card(rank, suit)
        # collections                This module implements specialized container datatypes providing
        # deck
        # do_stuff                   A function for doing stuff
        # function1
        # long_list
        # main
        # my_global_dict
        # my_global_str
        # os                         OS routines for NT or Posix depending on what system we're on.
        # pathlib
        # randint                    Return random integer in range [a, b], including both end points.
        # rien_de_rien
        # short_list
        # the_walrus_and_the_carpenter_were_walking_close_at_hand
        out2 = [a for a in out if 'Exception' in a]
        self.assertEqual(len([o for o in out if not o.startswith("_pydev_stop_at_break")]), 30)
        self.assertEqual(len(out2), 0)

        # Same results from -a option
        out = run_cmd(PApp, 'doc -1a')
        self.assertEqual(len([o for o in out if not o.startswith("_pydev_stop_at_break")]), 30)


        run_cmd(PApp, 'set missing exception_string')
        out = run_cmd(PApp, 'cat -1 -a')
        # /dynamic_test_code>cat -1 -a
        # A                          class A:
        # Card                       Exception: OSError('could not find class definition')
        # Foo                        class Foo:
        # FrenchDeck                 class FrenchDeck:
        # Ten                        class Ten:
        # VerboseAttribute           class VerboseAttribute:
        # __builtins__               Exception: TypeError('module, class, method, function, traceback, frame, or code object was expected, got dict')
        # __cached__                 Exception: TypeError('module, class, method, function, traceback, frame, or code object was expected, got str')
        # __doc__                    Exception: TypeError('module, class, method, function, traceback, frame, or code object was expected, got NoneType')
        # __file__                   Exception: TypeError('module, class, method, function, traceback, frame, or code object was expected, got str')
        # __loader__                 Exception: TypeError('module, class, method, function, traceback, frame, or code object was expected, got SourceFileLoader')
        # __name__                   Exception: TypeError('module, class, method, function, traceback, frame, or code object was expected, got str')
        # __package__                Exception: TypeError('module, class, method, function, traceback, frame, or code object was expected, got str')
        # __spec__                   Exception: TypeError('module, class, method, function, traceback, frame, or code object was expected, got ModuleSpec')
        # a                          Exception: TypeError('module, class, method, function, traceback, frame, or code object was expected, got A')
        # beer_card                  Exception: TypeError('module, class, method, function, traceback, frame, or code object was expected, got Card')
        # collections                '''This module implements specialized container datatypes providing
        # deck                       Exception: TypeError('module, class, method, function, traceback, frame, or code object was expected, got FrenchDeck')
        # do_stuff                   def do_stuff():
        # function1                  def function1(my_param:str):
        # long_list                  Exception: TypeError('module, class, method, function, traceback, frame, or code object was expected, got list')
        # main                       def main():
        # my_global_dict             Exception: TypeError('module, class, method, function, traceback, frame, or code object was expected, got dict')
        # my_global_str              Exception: TypeError('module, class, method, function, traceback, frame, or code object was expected, got str')
        # os                         r"""OS routines for NT or Posix depending on what system we're on.
        # pathlib                    import fnmatch
        # randint                        def randint(self, a, b):
        # rien_de_rien               Exception: TypeError('module, class, method, function, traceback, frame, or code object was expected, got NoneType')
        # short_list                 Exception: TypeError('module, class, method, function, traceback, frame, or code object was expected, got list')
        # the_walrus_and_the_carpenter_were_walking_close_at_hand  Exception: TypeError('module, class, method, function, traceback, frame, or code object was ex…
        out2 = [a for a in out if 'Exception' in a]
        self.assertEqual(len([o for o in out if not o.startswith('_pydev_stop_at_break')]), 30)
        self.assertEqual(len(out2), 18)

        # info cmds with arg not found should show a perror, not raise an exception
        out = run_cmd(PApp, 'cat fjk/fjk', errs=True, norm=False)
        self.assertTrue('No such path' in out)

        out = run_cmd(PApp, 'doc -1 fjk/fjk', errs=True, norm=False)
        self.assertTrue('No such path' in out)


if __name__ == '__main__':
    PApp = pobmain.Pobiverse(,,,
    run_cmd(PApp, 'set contents true')
    run_cmd(PApp, 'set _static false')
    run_cmd(PApp, 'set width 120')

    # PApp = pob.shell()
    # PApp = Pobiverse(inspect.currentframe().f_back, *args, **kwargs)

    unittest.main(exit=False)

    PApp.do_exit('')
    del PApp
    print('Done testing')
