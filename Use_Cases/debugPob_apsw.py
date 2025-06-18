
import apsw

# NB some variables here have _prefix names because 'ls' of this scope namespace is part of Transcript Test
#   transcript_debugPob_all_4be16d15420a432bb7ad09af88b0c001.txt
import os as _os
_usecase_dir = _os.path.dirname(__file__)
_dbfile = _os.path.join(_usecase_dir, "../Tests/montypython.sqlite")
connection=apsw.Connection(_dbfile)
cursor=connection.cursor()
res = cursor.execute("select tbl_name, 'main' as schema from sqlite_master")

import pobshell
pobshell.shell()
