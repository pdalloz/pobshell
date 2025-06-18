"""
Run the test suite.  Parts of ancilliary code for setup and running commands were pinched from Cmd2
"""
import sys
import unittest

import re

from contextlib import (
    redirect_stderr,
    redirect_stdout,
)

from cmd2.utils import (
    StdSim,
)


# import some_python_to_explore

# Modules with python code to explore:
import sample_pirate
import sample_various

import pobshell
from pobshell import strpath

POB = None
# assert sympy.__version__ == '1.9'  # some tests rely on a specific version of sympy


# TODO
#       *   Test pobshell initialization with root= container and/or sequence objects, including sys.module
#           then try to cd into a backticked name, e.g. / ▶ cd `'email.message'`
#           And check new directory is the correct one.
#       *   Test that rootns has an entry for __builtins__
#           It's a PobNS object, so it has the dunders expected for a dict, but should def have
#               __builtins__, and this is often be useful for checking info on builts
#       *   Test that backticked paths are iterated ok when cd'ing to an absolute path with more than one '/'
#           E.g. /> cd  /nested_list/`3`/`2`/`2`    (debugPob_nested_contents.py)
#       *   Test that all info funcs return str's, ie find's pattern match won't crash
# /pobshell ▶ mro *
# common                     (<class 'module'>, <class 'object'>)
# dirops                     (<class 'module'>, <class 'object'>)
# headless                   (<class 'function'>, <class 'object'>)
# pob_unparse                (<class 'module'>, <class 'object'>)
# pobmain                    (<class 'module'>, <class 'object'>)
# pobnode                    (<class 'module'>, <class 'object'>)
# shell                      (<class 'function'>, <class 'object'>)
# strpath                    (<class 'module'>, <class 'object'>)
# /pobshell ▶ find . -d1 --mro *module*
# Traceback (most recent call last):
#   File "/opt/anaconda3/envs/PyShEnv/lib/python3.9/site-packages/cmd2/cmd2.py", line 2396, in onecmd_plus_hooks
#     stop = self.onecmd(statement, add_to_history=add_to_history)
#   File "/opt/anaconda3/envs/PyShEnv/lib/python3.9/site-packages/cmd2/cmd2.py", line 2847, in onecmd

# ls -l .
# `2`                        '1'  <class 'str'>
# pwd
# /nested_list/`3`/`2`/`2`
#
# Confirm doc excludes builtins, but doc -b includes them
# /PV_instance ▶ doc undoc_header
# /PV_instance ▶ doc -b undoc_header
# ==> undoc_header <==
# str(object='') -> str
# str(bytes_or_buffer[, encoding[, errors]]) -> str

# Finding by id is failing
# /inspect/cleandoc ▶ id .
# cleandoc                   140421554923408
# /inspect/cleandoc ▶ cd ..
# /inspect ▶ find . -a --id *140421554923408* -l 4 --cmd 'id -v .'

# Some objects are refusing to show their doc, claiming to be a builtin
# /pobshell/pobnode ▶ doc /inspect/cleandoc
# /pobshell/pobnode ▶ ls /inspect/cleandoc/__doc__
# __doc__
# /pobshell/pobnode ▶ value /inspect/cleandoc/__doc__
# ==> __doc__ <==
# ('Clean up indentation from docstrings.\n'
#  '\n'
#  '    Any whitespace that can be uniformly removed from the second line\n'
#  '    onwards is removed.')



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
    """Clear out and err StdSim buffers, run the command, and out, err """
    # return stdout if errs=False or stderr if errs=True"""
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

    if norm:
        err = normalize_lines(copy_stderr.getvalue())
        out = normalize_lines(copy_cmd_stdout.getvalue())
    else:
        err = copy_stderr.getvalue()
        out = copy_cmd_stdout.getvalue()

    return err, out

    # if errs:
    #     return normalize_lines(copy_stderr.getvalue()) if norm else copy_stderr.getvalue()
    # return normalize_lines(copy_cmd_stdout.getvalue()) if norm else copy_cmd_stdout.getvalue()


class test_Pobiverse(unittest.TestCase):

    def test_parentpath(self):
        run_cmd(POB, 'cd /')

        # Absolute paths don't reference POB nodes, they're abstract string manipulation
        self.assertEqual(strpath.dirname('/'), '/')
        self.assertEqual(strpath.dirname('/xyzzy'), '/')
        self.assertEqual(strpath.dirname('/nonesuch'), '/')
        self.assertEqual(strpath.dirname('/xyzzy/sub_xyzzy'), '/xyzzy')

        run_cmd(POB, 'cd sympy')
        self.assertEqual(strpath.dirname(POB.normpath('.')), '/')

        run_cmd(POB, 'cd /sympy/integrals')
        self.assertEqual(strpath.dirname('sympy/geometry'), 'sympy')

        run_cmd(POB, 'cd /')


    def test_abspath(self):
        run_cmd(POB, 'cd /')

        # Absolute paths don't reference POB nodes, they're abstract string manipulation
        self.assertEqual(POB.normpath('/'), '/')
        self.assertEqual(POB.normpath('/dummy_name'), '/dummy_name')

        # Relative paths
        self.assertEqual(POB.normpath('Pirate'), '/Pirate')
        self.assertEqual(POB.normpath('Pirate/cmdloop'), '/Pirate/cmdloop')

        self.assertEqual(POB.normpath('/Pirate/..'), '/')
        self.assertEqual(POB.normpath('..'), '/')

        self.assertEqual(POB.normpath('/Pirate/cmdloop/..'), '/Pirate')
        self.assertEqual(POB.normpath('/Pirate/cmdloop/../'), '/Pirate')
        self.assertEqual(POB.normpath('/Pirate/cmdloop/../__dict__'), '/Pirate/__dict__')

        self.assertEqual(POB.normpath('/Pirate/cmdloop'), '/Pirate/cmdloop')

        run_cmd(POB, 'cd /Pirate')
        # sibling directory
        self.assertEqual(POB.normpath('../Fg'), '/Fg')

        run_cmd(POB, 'cd /Pirate/cmdloop')
        self.assertEqual(POB.normpath('../..'), '/')

        run_cmd(POB, 'cd /Pirate/cmdloop/__dict__')
        self.assertEqual(POB.normpath('../../..'), '/')
        self.assertEqual(POB.normpath('../..'), '/Pirate')

        run_cmd(POB, 'cd /')


    def test_cd(self):
        run_cmd(POB, 'cd /')
        run_cmd(POB, 'cd /Pirate/cmdloop/')
        self.assertEqual(POB.curr_path.abspath, '/Pirate/cmdloop')
        run_cmd(POB, 'cd /')


    def test_zzzfind(self):
        # add zzz's to name so its run last
        run_cmd(POB, 'cd /sympy')

        # check that -winner works
        run_cmd(POB, 'set quiet false')
        # get results from stdout
        out = run_cmd(POB, "find /sympy/interactive -iname *version* -winner='-p.depth' --depthfirst", norm=True)
        # get Leader updates from stderr (since quiet is false)
        out2 = run_cmd(POB, 'find /sympy/interactive -iname *version* -winner="-p.depth" --depthfirst', norm=True,
                       errs=True)
        # check results
        self.assertEqual(len(out), 2)
        self.assertTrue(all(a.count('/') == 4 for a in out))  # check the two winners have depth of 4
        # check Leader updates
        self.assertEqual(len(out2), 2)
        self.assertTrue(all(a.startswith('[Leader') for a in out2))  # check for the two Leader updates

        # check that set quiet true suppresses 'Leader' updates
        run_cmd(POB, 'set quiet true')
        out = run_cmd(POB, "find /sympy/interactive -iname *version* -winner='-p.depth' --depthfirst", norm=True,
                      errs=True)
        self.assertEqual(len(out), 0)

        # check that limit 1 works, that and wildcard name matching works

        out = run_cmd(POB, "find . -name trun* --depthfirst -limit 1 -maxdepth 5", norm=True)
        self.assertEqual(out, ['/sympy/Poly/trunc'])

        # check that find -a searches within hidden namepaces
        out = run_cmd(POB, "find -a -maxdepth 3 /sympy/And -name *r*p* --depthfirst -limit 5", norm=True)
        # "find -a -maxdepth 3 /sympy/And -name *r*p* --depthfirst -limit 5"
        self.assertEqual(out[-1], "sympy/And/__and__/__call__/__repr__")
        # self.assertEqual(out[-1], "/sympy/And/__and__/__new__/__repr__")

        # Test recursive find
        # check that limit works and quoted python expression without an equals sign
        out = run_cmd(POB, 'find /sympy -name sin --depthfirst -print "p.abspath" -limit 4', norm=True)
        self.assertEqual(len(out), 4)

        # out = run_cmd(POB, 'find /sympy -name sin --depthfirst -print p.abspath', norm=True)  # non-determistic for dynamic attributes
        out = run_cmd(POB, 'find /sympy -maxdepth 5 -name sin -print p.abspath', norm=True)

        sample_expected_results = ['/sympy/algebras/quaternion/sin',
                                   '/sympy/core/compatibility/gmpy/sin', '/sympy/core/evalf/mp/sin',
                                   '/sympy/core/function/mpmath/FPContext/sin',
                                   '/sympy/core/function/mpmath/ctx_fp/cmath/sin',
                                   '/sympy/core/function/mpmath/ctx_fp/function_docs/sin',
                                   '/sympy/core/function/mpmath/ctx_fp/math2/sin', '/sympy/core/function/mpmath/fp/sin',
                                   '/sympy/core/function/mpmath/iv/sin', '/sympy/core/function/mpmath/sin',
                                   '/sympy/discrete/transforms/sin',
                                   '/sympy/functions/combinatorial/numbers/sin',
                                   '/sympy/functions/elementary/trigonometric/sin',
                                   '/sympy/functions/sin', '/sympy/functions/special/bessel/sin',
                                   '/sympy/functions/special/elliptic_integrals/sin',
                                   '/sympy/functions/special/error_functions/sin',
                                   '/sympy/functions/special/gamma_functions/sin',
                                   '/sympy/functions/special/hyper/sin',
                                   '/sympy/functions/special/mathieu_functions/sin',
                                   '/sympy/functions/special/spherical_harmonics/sin', '/sympy/geometry/ellipse/sin',
                                   '/sympy/geometry/entity/sin',
                                   '/sympy/geometry/plane/sin', '/sympy/geometry/polygon/sin',
                                   '/sympy/integrals/meijerint/sin',
                                   '/sympy/integrals/transforms/sin', '/sympy/integrals/trigonometry/sin',
                                   '/sympy/matrices/dense/sin',
                                   '/sympy/plotting/intervalmath/lib_interval/sin', '/sympy/plotting/intervalmath/sin',
                                   '/sympy/polys/numberfields/sin', '/sympy/polys/ring_series/sin', '/sympy/sin',
                                   '/sympy/solvers/ode/nonhomogeneous/sin', '/sympy/solvers/ode/systems/sin',
                                   '/sympy/solvers/solvers/sin']

        for r in sample_expected_results:
            self.assertIn(r, out)

        # check number of results
        self.assertEqual(len(out), 387)  # NB running in terminal gives different result count due to
        #     a bunch of paths beginning /sympy/testing/runtests/pdoctest/unittest/...
        #     Those paths don't show in results here.  I assume its a unittest thing


    def test_ls(self):
        run_cmd(POB, 'cd /sympy')

        # check ls -a contents matches dir()
        out = normalize_cols(run_cmd(POB, 'ls -1a', norm=False))
        self.assertEqual(out, dir(sympy))

        out = normalize_cols(run_cmd(POB, 'ls -a', norm=False))
        self.assertEqual(sorted(out), dir(sympy))

        # ls should work with . as argument
        out = run_cmd(POB, 'ls .')
        self.assertEqual(out, ['sympy'])

        # ls should match a provided glob pattern
        out = normalize_cols(run_cmd(POB, 'ls z*', norm=False))
        self.assertEqual(len(out), 3)

        assert POB._hide_prefixes == ['_']
        # list non hidden
        out = normalize_cols(run_cmd(POB, 'ls', norm=False))
        self.assertEqual(len(out), 908)
        # list hidden
        out = normalize_cols(run_cmd(POB, 'ls _*', norm=False))
        self.assertEqual(len(out), 12)
        # list all
        out = normalize_cols(run_cmd(POB, 'ls *', norm=False))
        self.assertEqual(len(out), 920)

        out = normalize_cols(run_cmd(POB, 'ls *ltj*', norm=False))
        self.assertEqual(out, ['stieltjes'])

        # ls with arg not found should show a perror, not raise an exception
        run_cmd(POB, 'cd /')
        out = run_cmd(POB, 'ls sy*/*', errs=True, norm=False)
        self.assertTrue('No such path' in out)

        # ls with arg not found should show a perror, not raise an exception
        out = run_cmd(POB, 'ls sympy/fjk', errs=True, norm=False)
        self.assertTrue('No such path' in out)

        # ls with arg not found should show a perror, not raise an exception
        out = run_cmd(POB, 'ls fjk/fjk', errs=True, norm=False)
        self.assertTrue('No such path' in out)

        # ls with arg not found should show a perror, not raise an exception
        out = run_cmd(POB, 'ls fjk/', errs=True, norm=False)
        self.assertTrue('No such path' in out)

        # ls with arg not found should show a perror, not raise an exception
        out = run_cmd(POB, 'ls /fjk', errs=True, norm=False)
        self.assertTrue('No such path' in out)

        out = run_cmd(POB, 'ls -x /sympy/Nor', norm=True)
        self.assertTrue("    doc                    Logical NOR function." in out)

        # validate ls -x output
        run_cmd(POB, 'cd /sympy/And')

        run_cmd(POB, 'set missing empty_string')
        out = run_cmd(POB, 'ls -x')
        self.assertEqual(len(out), 535)

        run_cmd(POB, 'set missing suppress_line')
        out = run_cmd(POB, 'ls -x')
        #  20220503 PSD I Have not verified the count delta below compared to static attributes count
        #               but its due to classmethods so seems ok
        self.assertEqual(len(out), 346)

        run_cmd(POB, 'set missing exception_string')
        out = run_cmd(POB, 'ls -x')
        out2 = [a for a in out if 'Exception' in a]
        self.assertEqual(len(out), 535)
        self.assertEqual(len(out2), 74)  # Delta from static attributes not looked at


    def test_settables(self):
        # check that col 1 is 25 chars for short names
        run_cmd(POB, 'set ll_col1_width 25')
        out = run_cmd(POB, 'ls -l /sympy/N', norm=False)
        self.assertTrue(out.startswith("N                          <"))

        # check that col 1 is as long as necessary for long names, and adds 2 spaces before rest of entry
        out = run_cmd(POB, "ls -l /sympy/ImmutableDenseMatrix/strongly_connected_components_decomposition", norm=False)
        self.assertTrue(out.startswith("strongly_connected_components_decomposition  <"))

        # check that col 1 picks up user setting when default width is changed
        run_cmd(POB, 'set ll_col1_width 30')
        out = run_cmd(POB, 'ls -l /sympy/N', norm=False)
        self.assertTrue(out.startswith("N                               <"))

        run_cmd(POB, 'set ll_col1_width 25')



    def test_info_cmds(self):
        run_cmd(POB, 'cd /Pirate')

        # doc -1 should return one liner with object name and its doc string for object that have one
        out = run_cmd(POB, 'doc -1 yo_parser')
        assert(len(out) == 1)
        self.assertTrue(out[0].startswith('yo_parser'))
        self.assertTrue(out[0].endswith('Custom ArgumentParser class that improves error and help output'))


        # doc with a pattern should only doc the names in the namespace that match the pattern
        # /Pirate ▶ doc -1 post*
        # postcmd                    Runs right before a command is about to return.
        # postloop                   Hook method executed once when the :meth:`~.cmd2.Cmd.cmdloop()`
        out = run_cmd(POB, 'doc -1 post*')
        self.assertTrue(len(out), 2)

        # test signature with something that has a signature
        out = run_cmd(POB, 'signature -1 /Pirate/select')

        # test signature gives empty result set for something without a signature
        out = run_cmd(POB, 'signature -1 /Pirate/run_script_description')


        # test signature works with * and returns correct number of results, also test piping to shell

        # test signature works with * and returns correct number of results, also test piping to shell
        # test signature returns nothing for objects that have no signature
        self.assertEqual(out, ['827'])

        # test doc * excludes objects with no doc for appropriate set missing
        run_cmd(POB, 'cd /sympy/And')
        run_cmd(POB, 'set missing suppress_line')
        out = run_cmd(POB, 'cat -1 ')
        self.assertEqual(len(out), 33)  # differs from static case due to @classmethod functions
        out = run_cmd(POB, 'doc -1 ')
        self.assertEqual(len(out), 29)

        run_cmd(POB, 'set missing empty_string')
        out = run_cmd(POB, 'cat -1 ')
        out2 = [a for a in out if 'Exception' in a]
        self.assertEqual(len(out), 107)
        self.assertEqual(len(out2), 0)
        out = run_cmd(POB, 'doc -1 ')
        out2 = [a for a in out if 'Exception' in a]
        self.assertEqual(len(out), 107)
        self.assertEqual(len(out2), 0)

        run_cmd(POB, 'set missing exception_string')
        out = run_cmd(POB, 'cat -1 ')
        out2 = [a for a in out if 'Exception' in a]
        self.assertEqual(len(out), 107)
        self.assertEqual(len(out2), 74)  # Delta from static attributes not looked at

        # info cmds with arg not found should show a perror, not raise an exception
        out = run_cmd(POB, 'cat fjk/fjk', errs=True, norm=False)
        self.assertTrue('No such path' in out)

        out = run_cmd(POB, 'doc -1 fjk/fjk', errs=True, norm=False)
        self.assertTrue('No such path' in out)



    def test_eval_and_exec(self):
        # WIP 12 Dec
        # TODO: Confirm that assignments and imports are persistent in rootns, but not elsewhere

        run_cmd(POB, 'cd /Pirate')

        # doc -1 should return one liner with object name and its doc string for object that have one
        out = run_cmd(POB, 'doc -1 yo_parser')
        assert(len(out) == 1)
        self.assertTrue(out[0].startswith('yo_parser'))
        self.assertTrue(out[0].endswith('Custom ArgumentParser class that improves error and help output'))


        # doc with a pattern should only doc the names in the namespace that match the pattern
        # /Pirate ▶ doc -1 post*
        # postcmd                    Runs right before a command is about to return.
        # postloop                   Hook method executed once when the :meth:`~.cmd2.Cmd.cmdloop()`
        out = run_cmd(POB, 'doc -1 post*')
        self.assertTrue(len(out), 2)

        # test signature with something that has a signature
        out = run_cmd(POB, 'signature -1 /Pirate/select')

        # test signature gives empty result set for something without a signature
        out = run_cmd(POB, 'signature -1 /Pirate/run_script_description')


if __name__ == '__main__':
    POB = pobshell.headless(root=pirate)

    # TODO: Decide pobshell API for headless
    # run_cmd(pob, 'set static false')  WIP
    # TODO: Decide about these:
    run_cmd(POB, 'set contents true')
    run_cmd(POB, 'set static false')
    # run_cmd(POB, 'set static true')
    run_cmd(POB, 'set width 120')


    unittest.main(exit=False, failfast=True, verbosity=2)

    # loader = unittest.TestLoader()
    # suite = unittest.TestSuite()
    # tests_to_run = [test_PySh.test_zzzfind]
    # for test in tests_to_run:
    #     suite.addTests(loader.loadTestsFromTestCase(test))
    #     runner = unittest.TextTestRunner()
    #     runner.run(suite)

    POB.do_exit('')
    del POB
    print('Done testing')
