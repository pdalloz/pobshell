""" Derived from ast.unparse; this version returns a Pobshell path from a Python ast.
"""
from __future__ import print_function, unicode_literals
import six
import sys
import ast
import os
import tokenize
from six import StringIO
from .common import PobPrefs


# Large float and imaginary literals get turned into infinities in the AST.
# We unparse those infinities to INFSTR.
INFSTR = "1e" + repr(sys.float_info.max_10_exp + 1)

def interleave(inter, f, seq):
    """Call f on each item in seq, calling inter() in between.
    """
    seq = iter(seq)
    try:
        f(next(seq))
    except StopIteration:
        pass
    else:
        for x in seq:
            inter()
            f(x)

class Unparser:
    """Return pob path from python ast

    Methods in this class recursively traverse an AST and
    output a valid pypath suitable for Pobshell
        a.b -> a/b
        x[2] -> x/`2`

    Main difference from original is processing of contentkey path components
    """
    def __init__(self, tree, file=None):
        """Unparser(tree, file=sys.stdout) -> None.
         Print the source for tree to file."""
        if file:
            self.f = file
        else:
            self.f = StringIO("")

        self.future_imports = []
        self._indent = 0
        self.BTdispatch(tree)
        # self.dispatch(tree)
        print("", file=self.f)
        self.f.flush()


    def __repr__(self):
        self.f.seek(0)
        return self.f.read()


    def fill(self, text = ""):
        "Indent a piece of text, according to the current indentation level"
        self.f.write("\n"+"    "*self._indent + text)

    def write(self, text):
        "Append a piece of text to the current line."
        self.f.write(six.text_type(text))

    def enter(self):
        "Print ':', and increase the indentation."
        self.write(":")
        self._indent += 1

    def leave(self):
        "Decrease the indentation level."
        self._indent -= 1

    def dispatch(self, tree):
        "Dispatcher function, dispatching tree type T to method _T."
        if isinstance(tree, list):
            for t in tree:
                self.dispatch(t)
            return
        meth = getattr(self, "_"+tree.__class__.__name__)
        meth(tree)


    def BTdispatch(self, tree):
        "Dispatcher function, dispatching tree type T to method _T."
        if isinstance(tree, list):
            for t in tree:
                self.BTdispatch(t)
            return
        meth = getattr(self, "_BT"+tree.__class__.__name__)
        meth(tree)


    ############### Unparsing methods ######################
    # There should be one method per concrete grammar type #
    # Constructors should be grouped by sum type. Ideally, #
    # this would follow the order in the grammar, but      #
    # currently doesn't.                                   #
    ########################################################

    def _Module(self, tree):
        for stmt in tree.body:
            self.dispatch(stmt)

    def _BTModule(self, tree):
        for stmt in tree.body:
            self.BTdispatch(stmt)

    def _Expression(self, tree):
        self.dispatch(tree.body)

    def _BTExpression(self, tree):
        return self.BTdispatch(tree.body)

    # stmt
    def _Expr(self, tree):
        self.fill()
        self.dispatch(tree.value)

    def _BTExpr(self, tree):
        return self.BTdispatch(tree.value)


    def _NamedExpr(self, tree):
        self.write("(")
        self.dispatch(tree.target)
        self.write(" := ")
        self.dispatch(tree.value)
        self.write(")")

    def _BTNamedExpr(self, tree):
        self.write(PobPrefs.contentkey_delimiter)
        self._NamedExpr(tree)
        self.write(PobPrefs.contentkey_delimiter)


    # expr
    def _Bytes(self, t):
        self.write(repr(t.s))

    def _BTBytes(self, t):
        self.write(PobPrefs.contentkey_delimiter)
        self._Bytes(t)
        self.write(PobPrefs.contentkey_delimiter)


    def _Str(self, tree):
        self.write(repr(tree.s))

    def _BTStr(self, tree):
        if not tree.s.isidentifier():
            self.write(PobPrefs.contentkey_delimiter)
            self._Str(tree)
            self.write(PobPrefs.contentkey_delimiter)
        else:
            self._Str(tree)


    def _JoinedStr(self, t):
        # JoinedStr(expr* values)
        self.write("f")
        string = StringIO()
        self._fstring_JoinedStr(t, string.write)
        # Deviation from `unparse.py`: Try to find an unused quote.
        # This change is made to handle _very_ complex f-strings.
        v = string.getvalue()
        if '\n' in v or '\r' in v:
            quote_types = ["'''", '"""']
        else:
            quote_types = ["'", '"', '"""', "'''"]
        for quote_type in quote_types:
            if quote_type not in v:
                v = "{quote_type}{v}{quote_type}".format(quote_type=quote_type, v=v)
                break
        else:
            v = repr(v)
        self.write(v)

    def _BTJoinedStr(self, t):
        self.write(PobPrefs.contentkey_delimiter)
        self._JoinedStr(t)
        self.write(PobPrefs.contentkey_delimiter)


    def _FormattedValue(self, t):
        # FormattedValue(expr value, int? conversion, expr? format_spec)
        #   A formatted value (within a formatted string literal).
        #   For example, in the string f'hello {world!s}' the formatted value is world!s.
        self.write("f")
        string = StringIO()
        self._fstring_JoinedStr(t, string.write)
        self.write(repr(string.getvalue()))

    def _BTFormattedValue(self, t):
        # FormattedValue(expr value, int? conversion, expr? format_spec)
        self.write(PobPrefs.contentkey_delimiter)
        self._FormattedValue(t)
        self.write(PobPrefs.contentkey_delimiter)

    def _fstring_JoinedStr(self, t, write):
        for value in t.values:
            meth = getattr(self, "_fstring_" + type(value).__name__)
            meth(value, write)

    def _fstring_Str(self, t, write):
        value = t.s.replace("{", "{{").replace("}", "}}")
        write(value)

    def _fstring_Constant(self, t, write):
        assert isinstance(t.value, str)
        value = t.value.replace("{", "{{").replace("}", "}}")
        write(value)

    def _fstring_FormattedValue(self, t, write):
        write("{")
        expr = StringIO()
        Unparser(t.value, expr)
        expr = expr.getvalue().rstrip("\n")
        if expr.startswith("{"):
            write(" ")  # Separate pair of opening brackets as "{ {"
        write(expr)
        if t.conversion != -1:
            conversion = chr(t.conversion)
            assert conversion in "sra"
            write("!{conversion}".format(conversion=conversion))
        if t.format_spec:
            write(":")
            meth = getattr(self, "_fstring_" + type(t.format_spec).__name__)
            meth(t.format_spec, write)
        write("}")


    def _Name(self, t):
        self.write(t.id)

    def _BTName(self, t):
        self._Name(t)


    def _NameConstant(self, t):
        self.write(repr(t.value))

    def _BTNameConstant(self, t):
        self._NameConstant(t)


    def _Repr(self, t):
        self.write("repr(")
        self.dispatch(t.value)
        self.write(")")

    def _write_constant(self, value):
        if isinstance(value, (float, complex)):
            # Substitute overflowing decimal literal for AST infinities.
            self.write(repr(value).replace("inf", INFSTR))
        else:
            self.write(repr(value))


    def _Constant(self, t):
        # A constant value. The value attribute of the Constant literal contains the Python object it represents. The
        # values represented can be simple types such as a number, string or None, but also immutable container types
        # (tuples and frozensets) if all of their elements are constant.
        value = t.value
        if isinstance(value, tuple):
            self.write("(")
            if len(value) == 1:
                self._write_constant(value[0])
                self.write(",")
            else:
                interleave(lambda: self.write(", "), self._write_constant, value)
            self.write(")")
        elif value is Ellipsis: # instead of `...` for Py2 compatibility
            self.write("...")
        else:
            if t.kind == "u":
                self.write("u")
            self._write_constant(t.value)

    def _BTConstant(self, t):
        self.write(PobPrefs.contentkey_delimiter)
        self._Constant(t)
        self.write(PobPrefs.contentkey_delimiter)


    def _Num(self, t):
        repr_n = repr(t.n)
        if six.PY3:
            self.write(repr_n.replace("inf", INFSTR))
        else:
            # Parenthesize negative numbers, to avoid turning (-1)**2 into -1**2.
            if repr_n.startswith("-"):
                self.write("(")
            if "inf" in repr_n and repr_n.endswith("*j"):
                repr_n = repr_n.replace("*j", "j")
            # Substitute overflowing decimal literal for AST infinities.
            self.write(repr_n.replace("inf", INFSTR))
            if repr_n.startswith("-"):
                self.write(")")

    def _BTNum(self, t):
        self.write(PobPrefs.contentkey_delimiter)
        self._Num(t)
        self.write(PobPrefs.contentkey_delimiter)


    def _List(self, t):
        self.write("[")
        interleave(lambda: self.write(", "), self.dispatch, t.elts)
        self.write("]")

    def _BTList(self, t):
        self.write(PobPrefs.contentkey_delimiter)
        self._List(t)
        self.write(PobPrefs.contentkey_delimiter)


    def _ListComp(self, t):
        self.write("[")
        self.dispatch(t.elt)
        for gen in t.generators:
            self.dispatch(gen)
        self.write("]")

    def _BTListComp(self, t):
        self.write(PobPrefs.contentkey_delimiter)
        self._ListComp(t)
        self.write(PobPrefs.contentkey_delimiter)


    def _comprehension(self, t):
        if getattr(t, 'is_async', False):
            self.write(" async for ")
        else:
            self.write(" for ")
        self.dispatch(t.target)
        self.write(" in ")
        self.dispatch(t.iter)
        for if_clause in t.ifs:
            self.write(" if ")
            self.dispatch(if_clause)

    def _BTcomprehension(self, t):
        self.write(PobPrefs.contentkey_delimiter)
        self._comprehension(t)
        self.write(PobPrefs.contentkey_delimiter)


    def _IfExp(self, t):
        self.write("(")
        self.dispatch(t.body)
        self.write(" if ")
        self.dispatch(t.test)
        self.write(" else ")
        self.dispatch(t.orelse)
        self.write(")")

    def _BTIfExp(self, t):
        self.write(PobPrefs.contentkey_delimiter)
        self._IfExp(t)
        self.write(PobPrefs.contentkey_delimiter)


    def _Tuple(self, t):
        self.write("(")
        if len(t.elts) == 1:
            elt = t.elts[0]
            self.dispatch(elt)
            self.write(",")
        else:
            interleave(lambda: self.write(", "), self.dispatch, t.elts)
        self.write(")")

    def _BTTuple(self, t):
        self.write(PobPrefs.contentkey_delimiter)
        self._Tuple(t)
        self.write(PobPrefs.contentkey_delimiter)


    unop = {"Invert":"~", "Not": "not", "UAdd":"+", "USub":"-"}
    def _UnaryOp(self, t):
        self.write("(")
        self.write(self.unop[t.op.__class__.__name__])
        self.write(" ")
        if six.PY2 and isinstance(t.op, ast.USub) and isinstance(t.operand, ast.Num):
            # If we're applying unary minus to a number, parenthesize the number.
            # This is necessary: -2147483648 is different from -(2147483648) on
            # a 32-bit machine (the first is an int, the second a long), and
            # -7j is different from -(7j).  (The first has real part 0.0, the second
            # has real part -0.0.)
            self.write("(")
            self.dispatch(t.operand)
            self.write(")")
        else:
            self.dispatch(t.operand)
        self.write(")")

    def _BTUnaryOp(self, t):
        self.write(PobPrefs.contentkey_delimiter)
        self._UnaryOp(t)
        self.write(PobPrefs.contentkey_delimiter)


    binop = { "Add":"+", "Sub":"-", "Mult":"*", "MatMult":"@", "Div":"/", "Mod":"%",
                    "LShift":"<<", "RShift":">>", "BitOr":"|", "BitXor":"^", "BitAnd":"&",
                    "FloorDiv":"//", "Pow": "**"}
    def _BinOp(self, t):
        self.write("(")
        self.dispatch(t.left)
        self.write(" " + self.binop[t.op.__class__.__name__] + " ")
        self.dispatch(t.right)
        self.write(")")

    def _BTBinOp(self, t):
        self.write(PobPrefs.contentkey_delimiter)
        self._BinOp(t)
        self.write(PobPrefs.contentkey_delimiter)


    cmpops = {"Eq":"==", "NotEq":"!=", "Lt":"<", "LtE":"<=", "Gt":">", "GtE":">=",
                        "Is":"is", "IsNot":"is not", "In":"in", "NotIn":"not in"}
    def _Compare(self, t):
        self.write("(")
        self.dispatch(t.left)
        for o, e in zip(t.ops, t.comparators):
            self.write(" " + self.cmpops[o.__class__.__name__] + " ")
            self.dispatch(e)
        self.write(")")

    def _BTCompare(self, t):
        self.write(PobPrefs.contentkey_delimiter)
        self._Compare(t)
        self.write(PobPrefs.contentkey_delimiter)


    boolops = {ast.And: 'and', ast.Or: 'or'}
    def _BoolOp(self, t):
        self.write("(")
        s = " %s " % self.boolops[t.op.__class__]
        interleave(lambda: self.write(s), self.dispatch, t.values)
        self.write(")")

    def _BTBoolOp(self, t):
        self.write(PobPrefs.contentkey_delimiter)
        self._BoolOp(t)
        self.write(PobPrefs.contentkey_delimiter)


    def _Attribute(self,t):
        self.dispatch(t.value)
        # Special case: 3.__abs__() is a syntax error, so if t.value
        # is an integer literal then we need to either parenthesize
        # it or add an extra space to get 3 .__abs__().
        if isinstance(t.value, getattr(ast, 'Constant', getattr(ast, 'Num', None))) and isinstance(t.value.n, int):
            self.write(" ")
        self.write(".")
        self.write(t.attr)

    def _BTAttribute(self,t):
        self.BTdispatch(t.value)
        # Special case: 3.__abs__() is a syntax error, so if t.value
        # is an integer literal then we need to either parenthesize
        # it or add an extra space to get 3 .__abs__().
        if isinstance(t.value, getattr(ast, 'Constant', getattr(ast, 'Num', None))) and isinstance(t.value.n, int):
            self.write(" ")
        self.write("/")
        self.write(t.attr)


    def _Call(self, t):
        self.dispatch(t.func)
        self.write("(")
        comma = False
        for e in t.args:
            if comma: self.write(", ")
            else: comma = True
            self.dispatch(e)
        for e in t.keywords:
            if comma: self.write(", ")
            else: comma = True
            self.dispatch(e)
        if sys.version_info[:2] < (3, 5):
            if t.starargs:
                if comma: self.write(", ")
                else: comma = True
                self.write("*")
                self.dispatch(t.starargs)
            if t.kwargs:
                if comma: self.write(", ")
                else: comma = True
                self.write("**")
                self.dispatch(t.kwargs)
        self.write(")")

    def _BTCall(self, t):
        self.write(PobPrefs.contentkey_delimiter)
        self._Call(t)
        self.write(PobPrefs.contentkey_delimiter)


    def _Subscript(self, t):
        self.dispatch(t.value)
        self.write("[")
        self.dispatch(t.slice)
        self.write("]")

    def _BTSubscript(self, t):
        self.BTdispatch(t.value)
        self.write("/")
        self.BTdispatch(t.slice)
        # self.write("/")


    def _Starred(self, t):
        self.write("*")
        self.dispatch(t.value)

    def _BTStarred(self, t):
        self.write(PobPrefs.contentkey_delimiter)
        self._Starred(t)
        self.write(PobPrefs.contentkey_delimiter)


    # slice
    def _Ellipsis(self, t):
        self.write("...")

    def _BTEllipsis(self, t):
        self.write(PobPrefs.contentkey_delimiter)
        self._Ellipsis(t)
        self.write(PobPrefs.contentkey_delimiter)


    def _Index(self, t):
        self.dispatch(t.value)

    def _BTIndex(self, t):
        self.write(PobPrefs.contentkey_delimiter)
        self._Index(t)
        self.write(PobPrefs.contentkey_delimiter)


    def _Slice(self, t):
        if t.lower:
            self.dispatch(t.lower)
        self.write(":")
        if t.upper:
            self.dispatch(t.upper)
        if t.step:
            self.write(":")
            self.dispatch(t.step)

    def _BTSlice(self, t):
        self.write(PobPrefs.contentkey_delimiter)
        self._Slice(t)
        self.write(PobPrefs.contentkey_delimiter)


    def _ExtSlice(self, t):
        interleave(lambda: self.write(', '), self.dispatch, t.dims)

    def _BTExtSlice(self, t):
        self.write(PobPrefs.contentkey_delimiter)
        self._ExtSlice(t)
        self.write(PobPrefs.contentkey_delimiter)


    # argument
    def _arg(self, t):
        self.write(t.arg)
        if t.annotation:
            self.write(": ")
            self.dispatch(t.annotation)

    def _BTarg(self, t):
        self.write(PobPrefs.contentkey_delimiter)
        self._arg(t)
        self.write(PobPrefs.contentkey_delimiter)


    # others
    def _arguments(self, t):
        first = True
        # normal arguments
        all_args = getattr(t, 'posonlyargs', []) + t.args
        defaults = [None] * (len(all_args) - len(t.defaults)) + t.defaults
        for index, elements in enumerate(zip(all_args, defaults), 1):
            a, d = elements
            if first:first = False
            else: self.write(", ")
            self.dispatch(a)
            if d:
                self.write("=")
                self.dispatch(d)
            if index == len(getattr(t, 'posonlyargs', ())):
                self.write(", /")

        # varargs, or bare '*' if no varargs but keyword-only arguments present
        if t.vararg or getattr(t, "kwonlyargs", False):
            if first:first = False
            else: self.write(", ")
            self.write("*")
            if t.vararg:
                if hasattr(t.vararg, 'arg'):
                    self.write(t.vararg.arg)
                    if t.vararg.annotation:
                        self.write(": ")
                        self.dispatch(t.vararg.annotation)
                else:
                    self.write(t.vararg)
                    if getattr(t, 'varargannotation', None):
                        self.write(": ")
                        self.dispatch(t.varargannotation)

        # keyword-only arguments
        if getattr(t, "kwonlyargs", False):
            for a, d in zip(t.kwonlyargs, t.kw_defaults):
                if first:first = False
                else: self.write(", ")
                self.dispatch(a),
                if d:
                    self.write("=")
                    self.dispatch(d)

        # kwargs
        if t.kwarg:
            if first:first = False
            else: self.write(", ")
            if hasattr(t.kwarg, 'arg'):
                self.write("**"+t.kwarg.arg)
                if t.kwarg.annotation:
                    self.write(": ")
                    self.dispatch(t.kwarg.annotation)
            else:
                self.write("**"+t.kwarg)
                if getattr(t, 'kwargannotation', None):
                    self.write(": ")
                    self.dispatch(t.kwargannotation)


    def _BTarguments(self, t):
        self.write(PobPrefs.contentkey_delimiter)
        self._arguments(t)
        self.write(PobPrefs.contentkey_delimiter)


    def _keyword(self, t):
        if t.arg is None:
            # starting from Python 3.5 this denotes a kwargs part of the invocation
            self.write("**")
        else:
            self.write(t.arg)
            self.write("=")
        self.dispatch(t.value)


    def _BTkeyword(self, t):
        self.write(PobPrefs.contentkey_delimiter)
        self._keyword(t)
        self.write(PobPrefs.contentkey_delimiter)

