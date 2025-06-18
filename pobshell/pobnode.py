from __future__ import annotations   # allow constructor to reference own class, even though its not complete

import fnmatch
import inspect
import pprint
import warnings

from typing import TypeVar, Iterator, Union, Optional, Callable, Any

T = TypeVar('T', bound='Base')

from . import dirops
from . import strpath

import pprint as pp
import pydoc
from cmd2.ansi import style, Fg
from cmd2.utils import get_defining_class

from pygments import highlight

# noinspection PyUnresolvedReferences
from pygments.lexers.python import PythonLexer
from pygments.formatters.terminal import TerminalFormatter

from .dirops import PobNS
import collections.abc
from . import common
from .common import (PobPrefs, xtra_safe_repr, fmt_update_msg, temporary_setting, POBNODE_NAME, SELF_NAME, NoSuchInfo)

import ast
import builtins
from pympler import asizeof

# cache builtins for faster lookup
BUILTINS_SET = set(id(v) for v in vars(builtins).values())

# cache inspect function names and add isnative to the list
predicate_funcs = sorted([(func_name, func) for (func_name, func) in inspect.getmembers(inspect, inspect.isfunction)
                          if func_name.startswith('is')] + [('isdata', pydoc.isdata)])

def style_str(txt, style_code):
    return style(txt, fg=Fg[PobPrefs.current_theme[style_code]])


def exec_or_eval(code, global_ns, local_ns, expecting_eval=True):
    try:
        # Parse the code into an AST
        _ = ast.parse(code, mode='eval')
        # If no exception is raised, then it's an expression and can be eval'd
        result = eval(code, global_ns, local_ns)
        return 'eval', result
    except SyntaxError as se:
        # If a SyntaxError is raised, it's not an expression but a statement
        if expecting_eval:
            raise
        # Switch to exec mode
        exec(code, global_ns, local_ns)
        return 'exec', None



class AnsiDoc(pydoc.TextDoc):
    """Formatter class for text documentation."""

    _repr_instance = pydoc.TextRepr()
    repr = _repr_instance.repr

    def bold(self, text):
        """Highlight names, not going to use bold, going to use color"""
        return style(text, fg=Fg[PobPrefs.current_theme['path']])

    def section(self, title, contents):
        """Format a section with a given heading."""
        clean_contents = self.indent(contents).rstrip()
        return style(title, fg=Fg[PobPrefs.current_theme['type']]) + '\n' + clean_contents + '\n\n'



class PobNode:
    """ An object representing a Pobshell path and associated python objects
        self.abspath is its Pobshell path string
        self.rootpn is the root PobNode, whose .obj is PV.rootns (a PobNS instance)
        self.obj is the python object at this node in the hierarchy, given by path self.abspath
            self.obj for abspath=='/' is the root PobNS

        "info" properties  return information about self.obj; they wrap inspect and other utilities
            - cat, pprint, str, repr, doc, pydoc, signature, pypath, filepath, mro, type, typename, predicates,
              tree and memsize.
            They all return str's or NoSuchInfo Exception objects
              NoSuchInfos are returned when PobPrefs.prettify_infos is True and info retrieval raises an exception

        pathinfo property  reports info about object and its ancestors
            (supported by properties idpath, namepath, reprpath, and typepath)

        method eval_PYEXPR evaluate or executes python code in the namespace of self.obj

        Methods all_child_paths and filtered are generators that yield members of this namespace as PobNodes,
            for use by 'ls' command  (Pobiverse.do_ls) and info commands (Pobiverse.do_cat, do_value, ..)
                via Pobiverse.pobnodes_for_target
            and find command (Pobiverse.do_find)
                via PobNode method ns_walk which supports recursive walk of namespace hierarchy

        Attribute self.obj_path is a list of Python objects, from self.obj ancestor  from path and their ids,
            used by ns_walk to prune circular paths

        abspath is a pobpath a '/'-separated string of pobkeys 
            A pobkey is a string containing a python identifier or a contentkey
            A contentkey is a backtick delimited repr of the numeric index for a sequence or the key for a collection
            Examples of contentkey keys:  NB abspath elements don't include the double quotes.
                        "spam" - a valid python identifier
                        "`3`"   - a python int with value 3
                        "`'1/2'`"    - a python string containing a forward slash; a valid dict key
                        "`(2,42)`"    - a python tuple; a valid dict key

    """


    def __init__(self, pathstr: str, rootpn: Optional[T] = None, parent_node: Optional[T] = None,
                 obj: Optional[object] = common.ObjNone):
        """
        Initialise PobNode with rootpn and an absolute path, or parent_node and a key in its namespace

        Args:
            pathstr: a string with a single pobkey for parent_node namespace, or
                    or a sequence of / delimited pobkeys starting from root, or just /
            rootpn: Optional: the PobNode at path '/'
            parent_node: Optional: the PobNode object that is parent of this PobNode
            obj: Optional: The Python object at the path represented by this node
        """
        assert parent_node is not None or (rootpn is not None or pathstr == '/')


        # private reference to object at this path
        #   self.obj is a property that catches any warnings when self.obj is referenced
        self._obj = None

        if parent_node:  # Initialise from parent_node and a key in its namespace
            # Convert pathstr to a pobkey if it isn't one already (to_pobkey is idempotent)
            pobkey = dirops.to_pobkey(pathstr)
            self.name = pobkey

            self.rootpn = parent_node.rootpn
            self.abspath: str = strpath.join(parent_node.abspath, pobkey)

            # self.obj is the Python object at this path
            # if we were given obj, it saves us the trouble; otherwise we have to look it up:
            #   - it's the member associated with pobkey in the pob_namespace of parent's Python Object
            if obj is common.ObjNone:
                self.obj = dirops.get_pk_member(parent_node.obj, pobkey, exception_on_fail=True)
            else:
                self.obj = obj

            # whole python object ancestry from root; to avoid loops when find command recurses
            self.obj_path = parent_node.obj_path[:]
            self.obj_path.append(self.obj)

        elif rootpn:  # Initialise from rootpn and pathstr, a pobpath starting at root (ie absolute path of pobkeys)
            assert isinstance(pathstr, str) and strpath.isabs(pathstr) and (isinstance(rootpn, PobNode))
            self.abspath: str = pathstr  
            self.rootpn = rootpn

            self.name = '/' if self.abspath == '/' else strpath.basename(self.abspath)

            # use absolute path to iterate over python object ancestry from obj at '/'
            # used to avoid loops when find command recurses
            self.obj_path = dirops.obj_list_from_abspath(pathstr, rootpn.obj)


            if obj is common.ObjNone:
                # we weren't passed the Python object for this path,
                # but we calculated just above
                self.obj = self.obj_path[-1]
            else:
                # we were passed the Python object at this path
                self.obj = obj

        else:  # rootpn is None and parent_node is None:  This node as rootpn
            assert pathstr == '/'
            self.name = '/'            
            self.abspath = '/'
            self.rootpn = self
            self.obj = obj
            self.obj_path = [self.obj]




    @classmethod
    def init_from_root(cls, rootpn: PobNode, abspath: str):
        # initialise PobNode with a handle for rootns and an absolute pobpath
        return cls(pathstr=abspath, rootpn=rootpn)

    @classmethod
    def init_from_parent(cls, parent_node: T, skey: object, obj: Optional[object] = common.ObjNone):
        # initialise PobNode with obj: the object at this path,
        #             parent_node: a handle for parent PobNode,
        #             skey: a string; the key that retrieves object from parent
        return cls(pathstr=skey, parent_node=parent_node, obj=obj)


    @classmethod
    def init_as_root(cls, obj=common.ObjNone):
        # initialise PobNode with a handle for rootpn and an absolute pobpath
        return cls(pathstr='/', obj=obj)
    

    def __repr__(self):
        """repr of PobNode object"""
        try:
            if self.abspath == '/':
                return "<PobNode />"
            else:
                # truncate repr of any very large objects
                objstr = xtra_safe_repr(self.obj)[:500].replace('\n', ' ')
        except UnicodeDecodeError as e:
            objstr = repr(e)
        return '<PobNode ' + self.abspath + '::' + objstr + '>'


    def copy(self):
        return self.init_from_root(rootpn=self.rootpn, abspath=self.abspath)


    def childpn(self, key: object, val: object):
        """
        Returns an PobNode representing the child of this namespace having key as its name and val its Python object

        Used by info functions when iterating over the contents of a namespace, and by find when generating
            the paths to recurse into
        Args:
            key:  May be a string containing a python identifier, any valid dict key or sequence index object
            val:  Any Python object

        Returns: PobNode
            Represents a child PobNode of self; key gives its name and val its python object
            The child
                - Derives its abspath (absolute pobpath) by appending its name to self's abspath
        """
        #
        # key may be a str or any valid dict key such as int or tuple
        return PobNode(key, rootpn=None, parent_node=self, obj=val)

    @property
    def obj(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return self._obj

    @obj.setter
    def obj(self, new_val):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self._obj = new_val

    @obj.deleter
    def obj(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            del self._obj

    @property
    def parent_obj(self):
        """Return parent Python obj from path"""
        # N.B. obj_path[-1] is self.obj
        if len(self.obj_path) < 2:
            return None
        return self.obj_path[-2]

    def NoSuchInfo_result(self, result=''):
        # Common logic for PN.infoproperty results that are N/A or missing
        if not isinstance(result, common.NoSuchInfo):
            result = common.NoSuchInfo(result) if PobPrefs.prettify_infos else ''
        return result
    
    @property
    def _idpath(self) -> list[int]:
        return [id(o) for o in self.obj_path][1:]

    @property
    def _namepath(self) -> list[str]:
        return strpath.split_path_all(self.abspath)[1:]  # strip off blank name corresponding to root

    @property
    def _reprpath(self) -> list[str]:
        return [pprint.saferepr(o) for o in self.obj_path][1:]

    @property
    def _typepath(self):
        return [type(o) for o in self.obj_path][1:]

    @property
    def pathinfo(self):   # infoproperty   # 'infoproperty' tags PN properties implementing Pob commands
        """
        Return multiline string with (name, repr, type and id) for each ancestor object in self.abspath

        Used for reporting recursive paths found by search
        """
        res = [self.abspath]

        for n, r, t, i in zip(self._namepath, self._reprpath, self._typepath, self._idpath):
            namestr = style(f'name: {n}', fg=Fg[PobPrefs.current_theme['path']])
            res.append(f"{namestr}\n\t value:{r}\n\t type: {t}\n\t id: {i}")

        return "\n".join(res)


    def depth(self):
        if self.abspath == '/':
            return 0  # root, ie '/', is different, it has the same number of '/' chars as its children,
        return strpath.blanked_contentkeys(self.abspath).count('/')

    # ===========================================================================
    #
    #   Info functions implemented here as properties returning strings
    #       Their output is flexed by missing setting


    def handle_missing(self, info_func):   # TODO rename as normalize_info
        # evaluate info_func, returning result and catching exceptions and to return them as NoSuchInfo objects or ''

        # NB: PV.report_infos handles NoSuchInfo objects according to missing_info preference
        #   options are: skip_item, empty_string, exception_string
        # It's the job of individual PN.infomethods to handle infos that return `None`
        #   because that's a valid return value for some infos, but not all

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            # noinspection PyBroadException
            try:
                return info_func()
            except KeyboardInterrupt:
                raise
            # Any exception here indicates a missing info result
            except Exception as e:
                return self.NoSuchInfo_result(e)


    @property
    def cat(self) -> Union[str, common.NoSuchInfo]:  # infoproperty
        """
        Object's source code

        For a data descriptor returns concatenated code from fget, fset, and fdel
        When path is '/' and root object is a frame, relies on PobNS class cat method
        """

        def get_source_for_obj(o):
            """Helper that uses self.handle_missing to retrieve and format code for an object."""
            srclines = self.handle_missing(lambda: inspect.getsourcelines(o))
            if srclines == '' or isinstance(srclines, common.NoSuchInfo):
                return srclines  # Either '' or a NoSuchInfo instance.
            src, linenum = srclines
            # Add line numbers if enabled:
            src = ''.join(
                (f"{linenum + i}  " if PobPrefs.linenumbers else "") + line
                for i, line in enumerate(src)
            )
            return src

        # handle special case to return code when path is / and root object is a PobNS frame

        # --- Attempt to retrieve code for fget, fset, fdel ---
        parts = []
        if PobPrefs.simple_cat_and_doc:
            for method_name in ('fget', 'fset', 'fdel'):
                try:
                    func = dirops.get_member(self.obj, method_name)
                    if func is not None:
                        func_code = get_source_for_obj(func)
                        # If the retrieval for this method is valid (not '' or NoSuchInfo), add it:
                        if func_code and not isinstance(func_code, common.NoSuchInfo):
                            parts.append(func_code)

                except:  # Need a broad exception here, dynamic retrieval can give any kind of exception
                         #  e.g six module gives: "EXCEPTION of type 'ModuleNotFoundError' occurred with message: No module named '_gdbm'"
                    pass


        # If we found any descriptor sub-method code, join and return it (optionally highlight).
        if parts:
            joined_code = "\n".join(parts)
            if PobPrefs.prettify_infos:
                joined_code = highlight(joined_code, PythonLexer(),
                                        TerminalFormatter(bg=PobPrefs.current_theme['bg']))
            return joined_code

        # retrieve source for non-property objects,
        #   handling a special case for frame object at root /
        if self.abspath == '/' and isinstance(self.obj, PobNS) and PobPrefs.simple_cat_and_doc:
            code = self.obj.cat()
        else:
            code = get_source_for_obj(self.obj)
        if code == '' or isinstance(code, common.NoSuchInfo):
            # Return whatever was provided ('' or NoSuchInfo) respecting your missing_info config.
            return code

        # We got a string, highlight if needed:
        if PobPrefs.prettify_infos:
            code = highlight(code, PythonLexer(),
                                      TerminalFormatter(bg=PobPrefs.current_theme['bg']))
        return code


    @property
    def pprint(self) -> Union[str, common.NoSuchInfo]:   # infoproperty
        """
        String with pretty-printed representation of object
        """
        # no need for self.handle_missing here, every object should have a repr
        # - don't pretty print when PobPrefs.prettify_infos say not to
        #   because pretty print adds newlines that may break string pattern matching)
        return pp.pformat(self.obj) #if PobPrefs.prettify_infos else xtra_safe_repr(self.obj)

    @property
    def strval(self) -> Union[str, common.NoSuchInfo]:  # infoproperty
        """
        str() representation of object
        """
        # no need for self.handle_missing here, every object should have a repr
        #   because pretty print adds newlines that may break string pattern matching)
        return str(self.obj)  # if PobPrefs.prettify_infos else xtra_safe_repr(self.obj)

    @property
    def reprval(self) -> Union[str, common.NoSuchInfo]:  # infoproperty
        """
        repr() string representation of object
        """
        # no need for self.handle_missing here, every object should have a repr
        #   because pretty print adds newlines that may break string pattern matching)
        return xtra_safe_repr(self.obj)  # if PobPrefs.prettify_infos else xtra_safe_repr(self.obj)

    @property
    def doc(self) -> Union[str, common.NoSuchInfo]:   # infoproperty
        """
        Documentation string for object

        Use inheritance if map is 'mro'
        """
        if (PobPrefs.simple_cat_and_doc and type(self.obj).__module__ == 'builtins' and pydoc.isdata(self.obj)
              and not inspect.isdatadescriptor(self.obj)):
            # Don't document instances of list, str and similar objects, but do document property objects
            #   NB pydoc.isdata gives True for property objects
            return self.NoSuchInfo_result('Docstring excluded because simple_cat_and_doc setting is True')

        if PobPrefs.mro:
            # doc_result will be None or str; if str it will have been through cleandoc
            doc_result = self.handle_missing(lambda: inspect.getdoc(self.obj))
        else:
            # __doc__ attributes MIGHT return anything
            # e.g. pandas.core.arrays.categorical.cache_readonly.__doc__ is a getsetdescriptor
            doc_result = self.handle_missing(lambda: self.obj.__doc__)
            if type(doc_result) is str and PobPrefs.prettify_infos:
                doc_result = inspect.cleandoc(doc_result)

        if doc_result is None or (doc_result == '' and PobPrefs.simple_cat_and_doc):
            return self.NoSuchInfo_result()

        return str(doc_result)


    @property
    def pydoc(self) -> Union[str, common.NoSuchInfo]:   # infoproperty
        """
        Pydoc documentation string for object
        """
        return self.handle_missing(lambda: pydoc.render_doc(self.obj, title='%s',
                                                            renderer=AnsiDoc() if PobPrefs.prettify_infos else None))


    @property
    def signature(self) -> Union[str, common.NoSuchInfo]:   # infoproperty
        """
        String representation of signature of callable object
        """
        sig = self.handle_missing(lambda: inspect.signature(self.obj))
        if isinstance(sig, common.NoSuchInfo):
            return sig if PobPrefs.prettify_infos else ''
        if PobPrefs.prettify_infos:
            # don't highlight code when PobPrefs.prettify_infos say not to (ansi colors break string pattern matching)
            return highlight(str(sig), PythonLexer(), TerminalFormatter(bg=common.PobPrefs.current_theme['bg']))
        return str(sig)


    @property
    def pypath(self) -> str:   # infoproperty
        """
        Qualified Python name of object from its Pobshell abspath [experimental]
        """
        return dirops.pypath_from_obj_list(self.abspath, self.obj_path)


    @property
    def filepath(self) -> Union[str, common.NoSuchInfo]:   # infoproperty
        """
        OS path of file where object was defined (inspect.getfile)
        """
        return self.handle_missing(lambda: inspect.getfile(self.obj))


    @property
    def mro(self) -> Union[str, common.NoSuchInfo]:   # infoproperty
        """
        Tuple of base classes showing method resolution order for class, as a string
        """
        # TODO: Should this return mro of the instantiated class for instances too, similar to PN.abcs?
        res = self.handle_missing(lambda: inspect.getmro(self.obj))
        return res if isinstance(res, common.NoSuchInfo) else str(res)


    @property
    def which(self) -> Union[str, common.NoSuchInfo]:   # infoproperty
        """
        String representation of class where method object was defined [experimental]
        """
        res = self.handle_missing(lambda: get_defining_class(self.obj))
        if res is None:
            return self.NoSuchInfo_result()
        return str(res)


    @property
    def module(self) -> Union[str, common.NoSuchInfo]:  # infoproperty
        """
        Module where this object was defined [experimental]
        """
        res = self.handle_missing(lambda: inspect.getmodule(self.obj))
        if res is None:
            return self.NoSuchInfo_result()
        return str(res)


    @property
    def id(self) -> str:   # infoproperty
        """
        id of this object as a string
        """
        return str(id(self.obj))


    @property
    def type(self) -> str:   # infoproperty
        """
        This object's type as a string; str()
        """
        return str(type(self.obj))


    @property
    def typename(self) -> str:   # infoproperty
        """
        This object's type.__name__ attribute
        """
        return type(self.obj).__name__


    @property
    def memsize(self):   # infoproperty
        """
        Total memory size of object and members AS A STRING (pympler.asizeof)
        """
        return self.handle_missing(lambda: str(asizeof.asizeof(self.obj)))


    def memsize_comparison(self, test_str):
        size = self.handle_missing(lambda: str(asizeof.asizeof(self.obj)))
        if isinstance(size, NoSuchInfo):
            return False
        else:
            return eval(size + test_str, {})


    @property
    def predicates(self) -> Union[str, common.NoSuchInfo]:   # infoproperty
        """
        Return names of all inspect functions whose names start with 'is' and return True for object at this path
        """
        true_preds = [func_name for (func_name, func) in predicate_funcs if func(self.obj)]
        pred_matches = ' '.join(true_preds)
        if pred_matches:
            return pred_matches + ' '
        return self.NoSuchInfo_result()


    _abc_tuple = [(cls_name, getattr(collections.abc, cls_name)) for cls_name in dir(collections.abc) if
                  not cls_name.startswith('_')]

    @property
    def abcs(self) -> Union[str, common.NoSuchInfo]:   # infoproperty
        """Names of abstract base class interfaces implemented by this class or instance"""

        # if obj is a clas, report the abc classes it's a subclass of
        # if obj is an instance and PP.mro is True, report the abc classes it's an instance of
        abcmatch_func = issubclass if inspect.isclass(self.obj) else isinstance

        # """return a list of the names of the abstract base class interfaces matched by this class"""
        abcs_list = [cls_name for cls_name, cls in self._abc_tuple  if abcmatch_func(self.obj, cls)]
        abc_matches = ' '.join(abcs_list)

        if abc_matches:
            return abc_matches + ' '  # every item gets a leading and trailing space for easier pattern matching
        return self.NoSuchInfo_result()


    # Text symbols for tree branches and trunk
    SPACE = "    "
    BRANCH = "│   "
    TEE = "├── "
    LAST = "└── "

    def tree(self,
             prefix: str = "",
             depth: int = 1,
             exclude_func=None,
             prune_func=None,
             match_func=lambda x: True):
        """
        A single-function recursive tree generator. Yields lines (strings) that form
        a directory-like tree of this node and its descendants, subject to:

          - exclude_func(node): if True, the node is skipped entirely (excludes hidden objects)
          - prune_func(node): if True, node is included if it matches, but
                              we do NOT descend into its children.
          - match_func(node): if True, the node is 'included' unconditionally.
                              If False, it is included only if it has included children.

        A node is included if match_func(node) is True, OR at least one child is included.
        """

        # 1) Check if we should exclude this node entirely
        if exclude_func and exclude_func(self):
            return  # No lines yielded.

        # 2) If we've reached max depth, stop
        if depth < 0:
            return

        # 3) Gather potential children (already filtered by exclude_func in self.filtered())
        children = list(self.filtered(target_name_pattern='*',
                                      automagic=False,
                                      exclude_func=exclude_func))

        # If prune_func says "don't descend", skip children entirely
        included_children = []

        if not (prune_func and prune_func(self)) and depth > 0:
            # 4) Recurse on children to see which ones are "included"
            for child in children:
                # Collect the child's lines by calling child.tree with one less depth
                child_lines = list(child.tree(prefix="",  # We'll handle parent's pointer below
                                              depth=depth - 1,
                                              exclude_func=exclude_func,
                                              prune_func=prune_func,
                                              match_func=match_func))
                # If child_lines is non-empty, that child (or its subtree) is included
                if child_lines:
                    included_children.append(child_lines)

        # 5) Decide if *this* node is included
        #    We include it if match_func(self) is True OR if it has any included children.
        try:
            is_match = match_func is None or match_func(self)
        except (TypeError, ValueError):  # Some objects raise an exception when converted to truth value
            is_match = False

        if is_match or included_children:
            # -- YIELD the line for this node itself.
            # No pointer on the "self" line, because it's the top in this local subtree.
            yield (prefix +
                   f"{style_str(self.name, 'path')}  "
                   + xtra_safe_repr(self.obj)[:500].replace('\n', ' ')
                   + f"  {style_str(str(self.type), 'type')}")

            # 6) Yield lines for each included child, with pointer prefixes.
            # We have N included children; pointers are TEE for all but the last, and LAST for the final child.
            num_incl = len(included_children)
            for i, child_lines in enumerate(included_children):
                pointer = self.TEE if (i < num_incl - 1) else self.LAST
                extension = self.BRANCH if pointer == self.TEE else self.SPACE

                # We need to prepend "pointer" to the child's *first* line, and
                # prepend "extension" (│ or space) to subsequent lines.
                child_lines_iter = iter(child_lines)
                try:
                    first_child_line = next(child_lines_iter)
                except StopIteration:
                    # Shouldn't happen, because we only included children with non-empty lines
                    continue

                # yield the child's first line, with pointer
                yield prefix + pointer + first_child_line

                # then prepend extension for the child's remaining lines
                for line in child_lines_iter:
                    yield prefix + extension + line

        # else: no yield -> node is effectively excluded.



    def eval_PYEXPR(self, pyexpr, expecting_eval=False, noraise=False):
        """
        Evaluate or execute a Python expression in the context of this PobNode

        This method runs the provided Python expression (`pyexpr`) in a namespace built from:
        - A local namespace based on members of Python object at this path
        - A global namespace dictated by setting PobPrefs.global_ns

        If the special variables (identified by SELF_NAME and POBNODE_NAME) are not already present
        in the local namespace, they are temporarily inserted. These provide easy access to:
          - SELF_NAME: the Python object at the path where evaluation takes place (self.obj)
          - POBNODE_NAME: this PobNode instance (self)

        The expression is evaluated using with eval (if `expecting_eval` is True) or executed
        using exec (if False). During the evaluation/execution, the setting "prettify_infos" is temporarily
        disabled so PobNode methods such as PobNode.cat PobNode.pydoc return plain-text strings

        Parameters:
            pyexpr (str): The Python expression to evaluate or execute.
            expecting_eval (bool, optional): If True, the expression is expected to be evaluable (i.e. it
                                             returns a value). Otherwise, exec is used.
            noraise (bool, optional): If True, exceptions (other than KeyboardInterrupt) will not be raised;
                                      instead, a NoSuchInfo object containing the error message is returned.

        Returns:
            If expecting_eval is True:
                The result of evaluating the expression.
            Else:
                A tuple (out_type, res) where out_type indicates the type of output and res is the
                result from the execution.

        Raises:
            Exception: Propagates any exception encountered during eval/exec (except when noraise is True),
                       or a KeyboardInterrupt.
        """
        inserted_self = False
        inserted_pobnode = False

        # Set up the global namespace based on preferences.
        global_ns = {}
        if PobPrefs.global_ns is not None:
            if PobPrefs.global_ns.startswith('/') and PobPrefs.global_ns != self.abspath:
                globals_pn = PobNode(PobPrefs.global_ns, self.rootpn)
                global_ns = PobNS(globals_pn.obj, lazy=False).as_dict()
            elif PobPrefs.global_ns == 'user':
                global_ns = PobPrefs.user_namespace

        # Create the local namespace based on the current object's Python representation.
        local_ns = dirops.PobNS(self.obj, abspath=self.abspath, lazy=False)

        # Insert special variables if they are not already present.
        if SELF_NAME not in local_ns:
            local_ns[SELF_NAME] = self.obj
            inserted_self = True

        if POBNODE_NAME not in local_ns:
            local_ns[POBNODE_NAME] = self
            inserted_pobnode = True

        res = ''
        try:
            # Temporarily disable prettify_infos while evaluating/executing the expression.
            with temporary_setting('prettify_infos', False):
                out_type, res = exec_or_eval(pyexpr, global_ns, local_ns, expecting_eval)

            if expecting_eval:
                return res
            return out_type, res

        except KeyboardInterrupt:
            raise
        except Exception as e:
            if not noraise:
                raise
            return common.NoSuchInfo(str(e))

        finally:
            # Clean up by removing the temporary special variables.
            if inserted_pobnode:
                del local_ns[POBNODE_NAME]
            if inserted_self:
                del local_ns[SELF_NAME]
            # TODO: Maybe support assignments to names in root from eval_PYEXPR using local_ns._deltas



    def filtered(self, target_name_pattern: str, automagic: bool, exclude_func: Callable) -> Iterator[T]:
        """  Yield PobNode objects for each name in current namespace that matches target_name_pattern
             and is not ruled out by exclude_func(childpn)
        Args:
            target_name_pattern: glob pattern for name; '*' to match all names
            automagic: True if the magic in target_name_pattern was added automatically rather than from user
            exclude_func: function that accepts a pobnode and returns True if it should be excluded, False otherwise
        Returns:
            Yields PobNodes
        """

        pattern_matched = False
        # Loop over names and values in "namespace" of generic python object corresponding to self pobnode
        for k, v in dirops.get_pk_members(self.obj, exception_on_fail=False):
            if fnmatch.fnmatchcase(str(k), target_name_pattern):
                pattern_matched = True
                path: T = self.childpn(k, v)   # TODO will this raise dirops.PobMissingMemberException if needed?
                if not exclude_func or not exclude_func(path):  # maybe exclude hidden objects
                    yield path

        # if none of the children match the magic target_name_pattern
        #    then complain of No Such Path (unless automagic was to blame)
        if not pattern_matched and not automagic:
            raise dirops.PobMissingMemberException()


    def all_child_paths(self) -> Iterator[T]:
        for k, v in dirops.get_pk_members(self.obj, exception_on_fail=False):
            yield self.childpn(k, v)


    def ns_walk(self,
                pob,
                match_func: Optional[Callable],
                prune_prematch: Optional[Callable],
                prune_postmatch: Optional[Callable],
                max_depth: Optional[int],
                min_depth: Optional[int],
                find_flags: str,
                feedback_freq: Optional[int],
                explain_func: Optional[Callable],
                revisit_policy: str,
                noraise: bool,
                state: dict[str, Any] = None) -> Iterator[T]:
        """
        Args:
            pob:  Reference to main pobiverse object instance object, to get a handle on pfeedback method
            match_func:  Function returning True for objects that match the search criteria
            prune_prematch:  Function returning True for hidden objects (find's -a OPTION sets it to None)
            prune_postmatch:  Function returning True for paths that should be pruned after testing for match
            max_depth:  Don't recurse deeper than this depth.  Starting object is depth 0
            min_depth:  Don't report matches shallower than this depth.  Used for breadth first search kludge
            find_flags:  String containing chars indicating ns_walk decisions to debug
            feedback_freq: How frequently to output curr search node messages (1 in every feedback_freq nodes)
            explain_func:  Function returning True for Pobshell paths requiring full debug messaging
            revisit_policy: 'none', 'successes' or 'all'
                         revisit_policy is 'none': never revisit previously met objects (by id)
                         revisit_policy is 'successes' revisit previously met objects if we know we found a match
                                         walking them previously
                         revisit_policy is 'all': don't track visited object id's, revisit & rewalk everything
            noraise:  True if user wants to  ignore exceptions from matchpy or printpy evaluation
            state: state param is not passed by Pobiverse.do_find, it's a dict constructed by start PobNode node
                        which holds a data structure of shared state between nodes walked.
                        it's passed to each child node walked in the recursive call to ns_walk

                state contents:
                  debug_count: int,
                  visited: Optional[dict[T]],     - track objects on paths that were visited, for -uniq
                  successes: Optional[dict[T]],   - track objects on paths that led to matches so they'll be revisited

        Returns:  Yield every match from self and children

        """
        revisit_all = revisit_policy == 'all'
        revisit_successes = revisit_policy == 'successes'
        revisit_none = revisit_policy == 'none'

        curr_trace_walk = find_flags

        if max_depth is not None and self.depth() > max_depth:
            curr_trace_walk and debug_print(pob, 'DT',
                                            f"NOT VISITED: {self} is > max_depth",
                                            state=state, trace_walk=curr_trace_walk)
            # D -> Depth check failed;
            # T -> Not even tested
            return

        if state is None:
            state = {'debug_count': 0,
                     'visited': None if revisit_all else {},
                     'successes': None if revisit_all else {}}
                     # NB successes as are all nodes that yield a match, and their ancestors on the path
        else:
            state['debug_count'] += 1  # update count of nodes visited, for debug messaging

        previously_matched = None if state['successes'] is None else (id(self.obj) in state['successes'])

        # revisit logic ---------------

        # if revisit_policy is 'none',
        #    * we'll track visits (visited is a set {})
        #    * if 'none' is to mean strictly no dup results, we also need to track successes
        #    * we must check if node is in visited, if yes return BEFORE test-match-and-maybe-yield
        #    * we must check match-passing nodes against 'successes' before yielding
        #      because nodes that aren't walked do not get recorded in visited
        #         (since we don't know the outcome for their children)

        # if revisit_policy is 'successes'
        #   if node is in visited and was not a success, we should return BEFORE test-match-and-maybe-yield
        #   if node is not in visited then test-match the node and walk its children
        #       and enter it in visited *after* walking the children because only then do we know their outcome
        #         which dictates whether the node should be a success
        #   if node has been visited before and was a success, then treat it as not-in-visited
        #   Example:
        #   If 'd' was a previously met match on the path /a/b/c/d and now we're walking object c on path a/f/c
        #       - we know c has a child d that should match
        #           (but we'll re-walk and re-test because although slow, the code is simpler
        #            and its better for path-dependent criteria)
        #       - when d is tested and matches ok, objects a,b,c and d should all be added to successes
        #            so that if met again in future they'll be re-walked
        # NB revisit_policy='successes' will miss some path dependent matches
        #   due to pruning visited nodes that weren't successes when tested on previous visit (different paths tho)

        # if revisit_policy is 'all'
        #   test-match every node and walk all their children, don't track visits or successes

        if feedback_freq and (state['debug_count']>0) and (state['debug_count'] % feedback_freq ==0):
            pob.pfeedback(fmt_update_msg(f"  ({state['debug_count']}) {self.abspath}^"), end="")

        if explain_func:  # NB Must come after state['debug_count'] is initialised
            try:
                if explain_func(self):
                    curr_trace_walk = "*"  # -> Report all following decision points for this node
                    debug_print(pob, '*', f"EXPLAINING: {self.abspath}:" +
                                            f"\t(Successes={len(state['successes']) if state['successes'] is not None else 'None'})"
                                            , state=state, trace_walk=curr_trace_walk)
                                            # + f"\n{self.pathinfo}", state=state, find_flags=curr_trace_walk)
            except RecursionError:
                pob.perror(f"Recursion limit on deep path: {self.depth()} {self.abspath}")
                raise

        # prune hidden objects before checking for a match
        if prune_prematch and prune_prematch(self):
            # prune this path
            curr_trace_walk and debug_print(pob, 'TP', f"DON'T TEST:  {self.abspath} was pruned prematch",
                                            state=state, trace_walk=curr_trace_walk)
            # P -> Prune check failed
            # T -> Not even Tested
            return

        curr_trace_walk and debug_print(pob, 't', f"MATCH CHECK: {self}", state=state,
                                        trace_walk=curr_trace_walk)
        # t -> This node will be tested for a match.
        # Upper case debug flags track nodes being filtered out
        # Lower case debug flags track nodes on the path to a match, or being walked further

        # check if this path is a match ---------------------------------------

        is_match = False

        try:
            if not match_func or match_func(self):
                is_match = True
        except (TypeError, ValueError):  # Some objects raise an exception when converted to truth value
            if not noraise:
                raise

        if is_match:

            # keep a record of the nodes that led to this successful match, so they'll be revisited
            if state['successes'] is not None:  # only for revisit_all
                for obj_id in self._idpath:
                    state['successes'][obj_id] = self.obj
            #   This adds node to successes after mindepth test:
            #       If we're below mindepth we won't yield this node, but it will be in successes
            #       - if revisit_none and it's met again it won't be yielded because it appears a dup
            #           that's right behaviour, because if find is being iterated over mindepth
            #           the node will have been yielded by an earlier iteration of find having smaller mindepth
            #       - if revisit_successes or revisit_all and node is met again
            #           it will be yielded again, and that's ok

            if revisit_all or revisit_successes or not previously_matched:
                # ok to yield the node as a match if any of these are true
                #   - revisit_all (ie dups are ok)
                #   - revisit_successes (dups are ok)
                #   - revisit_none (only unique matches are ok) and not previously_matched

                # but we must also be above min_depth
                if min_depth is not None and self.depth() < min_depth:
                    # failed the depth test
                    curr_trace_walk and debug_print(pob, 'D',  # D -> Depth check failed
                                                    f"MATCHED BUT NOT YIELDED: {self} is < min_depth"
                                                    + f"(Successes={len(state['successes']) if state['successes'] is not None else 'None'})",
                                                    state=state, trace_walk=curr_trace_walk)
                else:
                    # We've found an acceptable match, yield it ********************************************************
                    curr_trace_walk and debug_print(pob, 'y', f"YIELD: {self} "
                                                    + f"(Successes={len(state['successes']) if state['successes'] is not None else 'None'})",
                                                    state=state, trace_walk=curr_trace_walk)
                    yield self


        # start of walk filter  ----------------------------------------------------------------------------------------
        #   Filter out paths we don't want to walk

        if prune_postmatch(self):
            curr_trace_walk and debug_print(pob, 'PW', f"DON'T WALK:  {self.abspath} was pruned postmatch",
                                            state=state, trace_walk=curr_trace_walk)
            # check if this path should be pruned (ie don't walk the children)
            #   By default prunes "primitive" types: detected with function is_primitive
            #   e.g. if find does not have '-a' param it excludes hidden attributes

            # P -> Prune check failed
            # W -> Was tested but won't Walk children
            return

        # Basic recursion protection, don't revisit an object that is an ancestor of itself.
        if PobPrefs.recursive_find_protection == 0:
            recursive = False
        else:  # protection level 1 and 2
            recursive = id(self.obj) in self._idpath[:-1]

        # protection level 2: Prune path if (name, type) were met earlier in path.
        # But don't prune submodules that have same name as parent, or names that match because they're contentkeys
        if not recursive and (PobPrefs.recursive_find_protection > 1) and (
                self.name in self.abspath[:-len(self.name)]):
            #  Don't treat as recursive contents having same index as earlier, or submodules with same name as parent
            if not (self.name.startswith(PobPrefs.contentkey_delimiter) or inspect.ismodule(self.obj)):
                recursive = (self.name, type(self.obj)) in zip(self._namepath[:-1], self._typepath[:-1])

        if recursive:
            curr_trace_walk and debug_print(pob, 'WR',
                                            f"DON'T WALK: {self.abspath, str(self.obj)[:300]} found a loop: current obj was also an ancestor: \n{self.pathinfo}",
                                            state=state, trace_walk=curr_trace_walk)
            # R -> Node failed Recursive path check
            # W -> Was tested but won't Walk children
            return

        if max_depth is not None and self.depth() == max_depth:
            curr_trace_walk and debug_print(pob, 'DW',
                                            f"DON'T WALK: {self.abspath, str(self.obj)[:300]} we're at max_depth already",
                                            state=state, trace_walk=curr_trace_walk)
            # D -> Depth test failed
            # W -> Was tested but won't Walk children
            return

        if revisit_none or revisit_successes:  # if either revisit policy is active
            # check if we've already tested this path and its children to this depth
            if id(self.obj) in state['visited'] and state['visited'][id(self.obj)] <= self.depth():
                # prune path if revisit_policy is 'none',
                #   or (policy is 'successes' and id(self.obj) not previously_matched)
                if revisit_none or not previously_matched:
                    curr_trace_walk and debug_print(pob, 'Vt',
                                                    f"DON'T REVISIT: {self.abspath}, {str(self.obj)[:35]} is visited no-match, "
                                                    + f"(succNodes={len(state['successes']) if state['successes'] is not None else 'None'} )"
                                                    + f"idpath:{self._idpath} ", state=state, trace_walk=curr_trace_walk)
                    # V -> Node failed already-Visited check
                    # t -> was tested already and may or may not have been yielded as a match
                    return

        # end of walk filter   -------------------------------------------------------------------------------------

        curr_trace_walk and debug_print(pob, 'w',
                                        f"WALK: path={self.abspath} \t\t:depth={self.depth()}:: {type(self.obj)} ",
                                        state=state, trace_walk=curr_trace_walk)
        # w -> Node was tested, now we'll walk the children

        # depth first search
        for c in self.all_child_paths():
            curr_trace_walk and debug_print(pob, 'c', f"\tWalk child {c.abspath}", state=state,
                                            trace_walk=curr_trace_walk)
            # c -> Now we'll walk this child node
            try:
                yield from c.ns_walk(pob, match_func, prune_prematch, prune_postmatch,
                                     max_depth, min_depth, find_flags, feedback_freq, explain_func, revisit_policy,
                                     noraise, state)
            except RecursionError as e:
                err_msg = common.short(str(e) + f"{self.abspath}")
                raise RecursionError(err_msg)

        if state['visited'] is not None:
            # Record that we've tested this path & all its children
            if (id(self.obj) not in state['visited']) or (state['visited'][id(self.obj)] > self.depth()):
                state['visited'][id(self.obj)] = self.depth()
            #   we record the depth at which this node was visited
            #       and if we've visited it at a shallower depth than before, we update the depth
            #       - the same node at a lower depth may have more descendents < maxdepth to be tested
            # Q: Why is this set AFTER walking children?
            # A: Because we only know if any descendants are a match after they're walked
            #       We should only filter out this node by 'visited' after all it's descendents have had a chance to
            #           add it to 'successes'

        curr_trace_walk and debug_print(pob, 'f', f"\tFINISHED visit {self}", state=state,
                                        trace_walk=curr_trace_walk)


def debug_print(pob, flag, *args, state: dict[str, any], trace_walk) -> None:
    # flag is str containing any chars from: D T P t m y P W R V w c f or *
    if ('*' in trace_walk or '*' in flag
            or any(f in trace_walk for f in flag)):
        pob.pfeedback(f"  ({state['debug_count']}) " + ' '.join([a for a in args]))
