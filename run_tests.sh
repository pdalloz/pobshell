#!/bin/sh
# Runs the three tests of the basic suite (docs/where-things-stand.md, section 2).
# Keep this script up to date whenever the test suite changes.
# HOME is set to .testhome in the repo folder (gitignored), so pobshell neither reads nor
# writes ~/.pobshell (pobshellrc, user_defs.py, history). It uses .testhome/.pobshell instead.
# That folder is not emptied between runs: a history file written by one run is still
# there for the next.
# The exit codes can't be relied on. Read the pass lines instead: "1 transcript passed",
# a last line "DONE", and two lines ending "test passed".
cd "$(dirname "$0")" || exit 1
HOME=$PWD/.testhome
mkdir -p "$HOME" || exit 1
export HOME
echo 'Transcript_Tests/transcript_debugPob_all_w10wsl_Py312_c001.txt *************:'
.venv/bin/python Use_Cases/debugPob_all.py --test Transcript_Tests/transcript_debugPob_all_w10wsl_Py312_c001.txt
echo ''
echo 'Use_Cases/testPob_getmembers.py *************:'
.venv/bin/python Use_Cases/testPob_getmembers.py < /dev/null
echo ''
echo 'Tests/test_frame_ref_release.py *************:'
.venv/bin/python Tests/test_frame_ref_release.py < /dev/null
