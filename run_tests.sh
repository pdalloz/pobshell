#!/bin/sh
# Runs the three tests of the basic suite (docs/where-things-stand.md, section 2).
# Keep this script up to date whenever the test suite changes.
# HOME is set to a new empty folder, so pobshell neither reads nor writes ~/.pobshell
# (pobshellrc, user_defs.py, history).
# The exit codes can't be relied on. Read the pass lines instead: "1 transcript passed",
# a last line "DONE", and two lines ending "test passed".
cd "$(dirname "$0")" || exit 1
HOME=$(mktemp -d "${TMPDIR:-/tmp}/pobtest.XXXXXX") || exit 1
export HOME
.venv/bin/python Use_Cases/debugPob_all.py --test Transcript_Tests/transcript_debugPob_all_w10wsl_Py312_c001.txt
.venv/bin/python Use_Cases/testPob_getmembers.py < /dev/null
.venv/bin/python Tests/test_frame_ref_release.py < /dev/null
