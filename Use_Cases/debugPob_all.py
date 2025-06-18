import apsw
import ast
import json
import math
import pandas
import sklearn
import sympy
import sys

# sklearn
from sklearn.datasets import load_iris
iris = load_iris()

# sympy
x = sympy.symbols("X")
eq = x + 1

# apsw

# NB some variables here have _prefix names because 'ls' of this scope namespace is part of Transcript Test
#   transcript_debugPob_all_4be16d15420a432bb7ad09af88b0c001.txt
import os as _os
_usecase_dir = _os.path.dirname(__file__)
_dbfile = _os.path.join(_usecase_dir, "../Tests/montypython.sqlite")
connection=apsw.Connection(_dbfile)
# connection=apsw.Connection("/Users/peterdalloz/Dropbox/PYTHONDROPBOX/pobshell/Tests/montypython.sqlite")
cursor=connection.cursor()

# ast
paths = [
	'''jskf['2'].jwui.vnn["3.4"]''',
	"""T[2][3]""",
	"(-b + math.sqrt(b**2-4*a*c))/(2*a)",
	"z['a']",
	"1/2",
	"sin(q)"
   ]

ast_trees = []
for p in paths:
	print(p)
	ast_trees.append(ast.parse(p))

# property
class Cafe:
	def __init__(self):
		self._menu_item = ""


	@property
	def we_have_got(self):
		self._menu_item += "spam "
		return self._menu_item + "eggs"


viking_cafe = Cafe()

#json
kson = json.loads('["foo", {"bar":["baz", null, 1.0, 2]}]') 

print('loaded all')
import pobshell
pobshell.shell()
# pobshell.shell(cmds='set allow_style never')
# pobshell.shell(root=kson)

# import cProfile
# import pobshell
# cProfile.run('pobshell.shell(persistent=True)', sort='time')



