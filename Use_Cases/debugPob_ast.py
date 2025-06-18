import ast
import sys
# sys.path.append('../pobshell')
# from ast import unparse

paths = [
    '''jskf['2'].jwui.vnn["3.4"]''',
    """jskf["2.3']"].jwui.vnn['3.4']""",
    '''jskf['2'].jwui[vnn]["'3']4"]''',
    """jskf[2].jwui.vnn["3[4]"]""",
    """Q[1.2]""",
    """T[2][3]""",
    """T[2.3]""",
    """T[2.3].q""",
    """DF.T[2.3].q""",
    """DF.T[2.3 ].q""",
    """T[(1,2)]""",
    """T[(1.2, 3)]""",
    """T[(1.2,2)]""",
    """T[(p,q)]""",
    """T[('1',"2")]""",
     "ab.c",
    "a['a.b'].c",
    "ab['']",
    "'ab.c'",
    "ab.c",
    "'ab.c'",
    "z['ab'].c",
    "z['ab'][c]",
    "z['ab' ][ c ]",
    "ab[ 'c']",
    "ab[' c']",
    "z[''].ab.c",
    "a",
    "z['a']",
    """z['"."']""",
    "",
    """z["'"].y['"'].x["''"].w['""'].u[x].t"""]

trees = []
for p in paths:
    print(p)
    trees.append(ast.parse(p))
import pobshell; pobshell.shell()
