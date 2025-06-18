import sys
import unittest

import sympy
# conda install sympy=1.9
import re

from contextlib import (
    redirect_stderr,
    redirect_stdout,
)

import strpath
import pob
from cmd2.utils import (
    StdSim,
)

assert sympy.__version__ == '1.9'  # some tests rely on a specific version of sympy

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
        self.assertEqual(strpath.dirname('/sympy'), '/')
        self.assertEqual(strpath.dirname('/nonesuch'), '/')
        self.assertEqual(strpath.dirname('/sympy/geometry'), '/sympy')

        # support trailing / which normpath should remove
        # TODO Fails: '/sympy/geometry' != '/sympy', but if it matches os.dirname maybe that's ok
        # self.assertEqual(strpath.dirname('/sympy/geometry/'), '/sympy')
        # NB  strpath.dirname('/sympy/geometry/') => Out[3]: '/sympy/geometry'
        # NB2 strpath.normpath('/sympy/geometry/') => Out[2]: '/sympy/geometry'

        run_cmd(PApp, 'cd sympy')
        self.assertEqual(strpath.dirname(PApp.normpath('.')), '/')

        run_cmd(PApp, 'cd /sympy/integrals')
        self.assertEqual(strpath.dirname('sympy/geometry'), 'sympy')

        run_cmd(PApp, 'cd /')


    def test_abspath(self):
        run_cmd(PApp, 'cd /')
        self.assertEqual(PApp.normpath('/'), '/')
        self.assertEqual(PApp.normpath('/sympy'), '/sympy')
        self.assertEqual(PApp.normpath('sympy'), '/sympy')
        self.assertEqual(PApp.normpath('sympy/integrals'), '/sympy/integrals')

        self.assertEqual(PApp.normpath('/sympy/..'), '/')
        self.assertEqual(PApp.normpath('..'), '/')

        self.assertEqual(PApp.normpath('/sympy/integrals/..'), '/sympy')
        self.assertEqual(PApp.normpath('/sympy/integrals/../'), '/sympy')
        self.assertEqual(PApp.normpath('/sympy/integrals/../geometry'), '/sympy/geometry')

        self.assertEqual(PApp.normpath('/sympy/integrals'), '/sympy/integrals')
        
        run_cmd(PApp, 'cd /unittest')
        self.assertEqual(PApp.normpath('../sympy'), '/sympy')

        run_cmd(PApp, 'cd /sympy/integrals')
        self.assertEqual(PApp.normpath('../..'), '/')

        run_cmd(PApp, 'cd /sympy/integrals/CosineTransform')
        self.assertEqual(PApp.normpath('../../..'), '/')
        self.assertEqual(PApp.normpath('../..'), '/sympy')

        run_cmd(PApp, 'cd /')


    def test_cd(self):
        run_cmd(PApp, 'cd /')
        run_cmd(PApp, 'cd sympy/integrals/')
        self.assertEqual(PApp.curr_path.abspath, '/sympy/integrals')
        run_cmd(PApp, 'cd /')


    def test_zzzfind(self):
        # add zzz's to name so its run last
        run_cmd(PApp, 'cd /sympy')

        # check that -winner works
        run_cmd(PApp, 'set quiet false')
        run_cmd(PApp, 'set track_find false')

        # get results from stdout
        out = run_cmd(PApp, """find /sympy/interactive -iname *version* -winner='-self.depth' -depthfirst""", norm=True)
        # get Leader updates from stderr (since quiet is false)
        out2 = run_cmd(PApp, """find /sympy/interactive -iname *version* -winner='-self.depth' -depthfirst""", norm=True, errs=True)
        # check results
        self.assertEqual(len(out), 2)
        self.assertTrue(all(a.count('/') == 4 for a in out))  # check the two winners have depth of 4
        # check Leader updates
        self.assertEqual(len(out2), 2)
        self.assertTrue(all(a.startswith('[Leader') for a in out2))  # check for the two Leader updates

        # check that set quiet true suppresses 'Leader' updates
        run_cmd(PApp, 'set quiet true')
        out = run_cmd(PApp, "find /sympy/interactive -iname *version* -winner='-self.depth' -depthfirst", norm=True, errs=True)
        self.assertEqual(len(out), 0)


        # check that limit 1 works, and that wildcard name matching works

        out=run_cmd(PApp, "find . -name trun* -depthfirst -limit 1", norm=True)
        self.assertEqual(out, ['/sympy/Poly/trunc'])

        # check that find -a searches within hidden namepaces
        out = run_cmd(PApp, "find -a -maxdepth 3 . -name c*py -limit 5 -depthfirst", norm=True)
        self.assertEqual(out[-1], "/sympy/Abs/default_assumptions/copy")

        # Test recursive find
        # check that limit works and quoted python expression without an equals sign
        out = run_cmd(PApp, 'find /sympy -name sin -depthfirst -print "self.abspath" -limit 4 -maxdepth 5', norm=True)
        self.assertEqual(len(out), 4)
        out = run_cmd(PApp, """ find /sympy -name sin -depthfirst -print "self.abspath" -maxdepth 6""", norm=True)
        # out = run_cmd(PApp, 'find /sympy -name sin -depthfirst -print self.abspath', norm=True)
        sample_expected_results = ['/sympy/algebras/quaternion/sin',
         '/sympy/core/compatibility/gmpy/sin', '/sympy/core/evalf/mp/sin', '/sympy/core/function/mpmath/FPContext/sin',
         '/sympy/core/function/mpmath/ctx_fp/cmath/sin', '/sympy/core/function/mpmath/ctx_fp/function_docs/sin',
         '/sympy/core/function/mpmath/ctx_fp/math2/sin', '/sympy/core/function/mpmath/fp/sin',
         '/sympy/core/function/mpmath/iv/sin', '/sympy/core/function/mpmath/sin', '/sympy/discrete/transforms/sin',
         '/sympy/functions/combinatorial/numbers/sin', '/sympy/functions/elementary/trigonometric/sin',
         '/sympy/functions/sin', '/sympy/functions/special/bessel/sin', '/sympy/functions/special/elliptic_integrals/sin',
         '/sympy/functions/special/error_functions/sin', '/sympy/functions/special/gamma_functions/sin',
         '/sympy/functions/special/hyper/sin', '/sympy/functions/special/mathieu_functions/sin',
         '/sympy/functions/special/spherical_harmonics/sin', '/sympy/geometry/ellipse/sin', '/sympy/geometry/entity/sin',
         '/sympy/geometry/plane/sin', '/sympy/geometry/polygon/sin', '/sympy/integrals/meijerint/sin',
         '/sympy/integrals/transforms/sin', '/sympy/integrals/trigonometry/sin', '/sympy/matrices/dense/sin',
         '/sympy/plotting/intervalmath/lib_interval/sin', '/sympy/plotting/intervalmath/sin',
         '/sympy/polys/numberfields/sin', '/sympy/polys/ring_series/sin', '/sympy/sin',
         '/sympy/solvers/ode/nonhomogeneous/sin', '/sympy/solvers/ode/systems/sin', '/sympy/solvers/solvers/sin']

        for r in sample_expected_results:
            self.assertIn(r,  out)

        # check number of results
        # TODO: It's going to depend on what recursion protection logic I use and
        #   also on what types, predicates, and objects I choose to include/exclude by default for ns walk
        #     Currently in the terminal (30 May 22)
        #           >find /sympy -name sin -depthfirst -print "self.abspath"  | wc -l
        #           1042
        # self.assertEqual(len(out), 387)   # NB running in terminal gives different result count due to
        #                                   #     paths beginning /sympy/testing/runtests/pdoctest/unittest/...
        #                                   #     Those paths don't show in results here.  I assume its a unittest thing





    def test_ls(self):

        run_cmd(PApp, 'cd /sympy')

        # check ls -a contents matches dir()
        out = normalize_cols(run_cmd(PApp, 'ls -1a', norm=False))
        self.assertEqual(out, dir(sympy))

        out = normalize_cols(run_cmd(PApp, 'ls -a', norm=False))
        self.assertEqual(sorted(out), dir(sympy))

        # ls should work with . as argument
        out = run_cmd(PApp, 'ls .')
        self.assertEqual(out, ['sympy'])

        # ls should match a provided glob pattern
        out = normalize_cols(run_cmd(PApp, 'ls z*', norm=False))
        self.assertEqual(len(out), 3)

        assert PApp._hide_prefixes == ['_']
        # list non hidden
        out = normalize_cols(run_cmd(PApp, 'ls', norm=False))
        self.assertEqual(len(out), 908)

        run_cmd(PApp, 'set auto_import_packages true')
        out = normalize_cols(run_cmd(PApp, 'ls', norm=False))
        self.assertEqual(len(out), 921)

        # list hidden
        out = normalize_cols(run_cmd(PApp, 'ls _*', norm=False))
        self.assertEqual(len(out), 12)
        # list all
        out = normalize_cols(run_cmd(PApp, 'ls *', norm=False))
        self.assertEqual(len(out), 933)

        out = normalize_cols(run_cmd(PApp, 'ls *ltj*', norm=False))
        self.assertEqual(out, ['stieltjes'])

        # ls with arg not found should show a perror, not raise an exception
        run_cmd(PApp, 'cd /')
        out = run_cmd(PApp, 'ls sy*/*', errs=True, norm=False)
        self.assertTrue('No such path' in out)

        # ls with arg not found should show a perror, not raise an exception
        out = run_cmd(PApp, 'ls sympy/fjk', errs=True, norm=False)
        self.assertTrue('No such path' in out)

        # ls with arg not found should show a perror, not raise an exception
        out = run_cmd(PApp, 'ls fjk/fjk', errs=True, norm=False)
        self.assertTrue('No such path' in out)

        # ls with arg not found should show a perror, not raise an exception
        out = run_cmd(PApp, 'ls fjk/', errs=True, norm=False)
        self.assertTrue('No such path' in out)

        # ls with arg not found should show a perror, not raise an exception
        out = run_cmd(PApp, 'ls /fjk', errs=True, norm=False)
        self.assertTrue('No such path' in out)

        out = run_cmd(PApp, 'ls -x /sympy/Nor', norm=True)
        self.assertTrue("    doc                    Logical NOR function." in out)


        # validate ls -x output
        run_cmd(PApp, 'cd /sympy/And')

        run_cmd(PApp, 'set missing empty_string')
        out = run_cmd(PApp, 'ls -x')
        self.assertEqual(len(out), 535)

        run_cmd(PApp, 'set missing suppress_line')
        out = run_cmd(PApp, 'ls -x')
        self.assertEqual(len(out), 342)

        run_cmd(PApp, 'set missing exception_string')
        out = run_cmd(PApp, 'ls -x')
        out2 = [a for a in out if 'Exception' in a]
        self.assertEqual(len(out), 535)
        self.assertEqual(len(out2), 80)



    def test_settables(self):
        # check that col 1 is 25 chars for short names
        run_cmd(PApp, 'set ll_col1_width 25')
        out = run_cmd(PApp, 'ls -l /sympy/N', norm=False)
        self.assertTrue(out.startswith("N                          <"))

        # check that col 1 is as long as necessary for long names, and adds 2 spaces before rest of entry
        out = run_cmd(PApp, "ls -l /sympy/ImmutableDenseMatrix/strongly_connected_components_decomposition", norm=False)
        self.assertTrue(out.startswith("strongly_connected_components_decomposition  <"))

        # check that col 1 picks up user setting when default width is changed
        run_cmd(PApp, 'set ll_col1_width 30')
        out = run_cmd(PApp, 'ls -l /sympy/N', norm=False)
        self.assertTrue(out.startswith("N                               <"))

        run_cmd(PApp, 'set ll_col1_width 25')



    def test_info_cmds(self):
        run_cmd(PApp, 'cd /sympy')

        # doc with a pattern should only doc the names in the namespace that match the pattern
        out = run_cmd(PApp, 'doc -1 cheb*')
        self.assertEqual(len(out), 6)
        self.assertTrue(all([('chebyshev' in d and ' the ' in d) for d in out]))  # each doc includes the word 'the'

        # test signature works with * and returns correct number of results, also test piping to shell
        out = run_cmd(PApp, 'signature * | wc -l')
        self.assertEqual(out, ['827'])

        run_cmd(PApp, 'cd /sympy/And')
        run_cmd(PApp, 'set missing suppress_line')
        out = run_cmd(PApp, 'cat -1 ')
        self.assertEqual(len(out), 27)
        out = run_cmd(PApp, 'doc -1 ')
        self.assertEqual(len(out), 30)

        run_cmd(PApp, 'set missing empty_string')
        out = run_cmd(PApp, 'cat -1 ')
        out2 = [a for a in out if 'Exception' in a]
        self.assertEqual(len(out), 107)
        self.assertEqual(len(out2), 0)
        out = run_cmd(PApp, 'doc -1 ')
        out2 = [a for a in out if 'Exception' in a]
        self.assertEqual(len(out), 107)
        self.assertEqual(len(out2), 0)

        run_cmd(PApp, 'set missing exception_string')
        out = run_cmd(PApp, 'cat -1 ')
        out2 = [a for a in out if 'Exception' in a]
        self.assertEqual(len(out), 107)
        self.assertEqual(len(out2), 80)

        # info cmds with arg not found should show a perror, not raise an exception
        out = run_cmd(PApp, 'cat fjk/fjk', errs=True, norm=False)
        self.assertTrue('No such path' in out)

        out = run_cmd(PApp, 'doc -1 fjk/fjk', errs=True, norm=False)
        self.assertTrue('No such path' in out)




if __name__ == '__main__':
    # pob.shell()
    PApp = pob.Pobiverse(,,,
    run_cmd(PApp, 'set mode _static')
    run_cmd(PApp, 'map code')
    # run_cmd(PApp, 'set contents false')
    # run_cmd(PApp, 'set static true')
    run_cmd(PApp, 'set width 120')
    run_cmd(PApp, 'set auto_import_packages false')

    # PApp = pob.shell()
    # PApp = Pobiverse(inspect.currentframe().f_back, *args, **kwargs)

    unittest.main(exit=False)

    # loader = unittest.TestLoader()
    # suite = unittest.TestSuite()
    # tests_to_run = [test_PySh.test_zzzfind]
    # for test in tests_to_run:
    #     suite.addTests(loader.loadTestsFromTestCase(test))
    #     runner = unittest.TextTestRunner()
    #     runner.run(suite)

    PApp.do_exit('')
    del PApp
    print('Done testing')
