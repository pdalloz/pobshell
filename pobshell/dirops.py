""" Various 'directory' operations

Retrieving members from arbitrary objects
handling pobkeys (contentkey delimited keys)

to_pobkey handles conversion of non-identifier keys to pobkeys (ie. wrap their repr in contentkey delimiters)
get_pk_members: For any object obj return a dict of all the k, v pairs where k is a pobkey and v is a python object
    Depends on commonPobPrefs.getitems_func which flexes members by
        * PobPrefs.contents setting True or False
            - NB attributes are always retrieved, tho may be hidden from listings or find by Python -> Pob map settings
        * retrieval mode dynamic or static
get_pk_member: Take a pobkey (attribute name or contentkey-delimited Python expression) and return associated member from obj
    If pobkey has contentkey delimiters, get_pk_member just iterates through keys from getmembers looking for a match
"""

import os
import inspect
import pprint
import sys
from inspect import isclass, getmro
from . import strpath, pob_inspect
from .common import ObjNone, PobPrefs, xtra_safe_repr, NoSuchInfo, short

from typing import List, Tuple, Optional

import io

from ast import literal_eval

from contextlib import redirect_stderr

import warnings
import types
import collections.abc
import pkgutil
from cmd2.utils import StdSim
import importlib



class Nonesuch(Exception):  # Just for debugging, never caught since never raised
    pass


def dict_delta(d1, d2):
    """
    Compute a delta dict that, when applied to d1,
    will update or add keys to match d2.
    (Keys in d1 that are not in d2 are left unchanged.)
    """
    return {k: d2[k] for k in d2 if k not in d1 or d1[k] is not d2[k]}
    # NB apply delta to d like this:
    #   result = d.copy()
    #   result.update(delta)


def frame_vars(f) -> dict:
    """ return a dict of locals & globals for frame f

    Args:
        f: a frame object from inspect.getframeinfo

    Returns:
        a dict of f's variables
    """
    namespace = {}
    namespace.update(f.f_globals)
    namespace.update(f.f_locals)
    return dict(sorted(namespace.items()))


class PobNS:
    # PobNamespace object
    # A dict wrapper with lazy initialization, with namespace of obj

    # PobNS objects:
    #   - used fleetingly for evaluation of user python expressions by PN.eval_PYEXPR
    #   - plus a persistent instance used to represent the root pob_namespace with path '/'


    def __new__(cls, obj, *args, **kwargs):
        # If obj is already a PobNS, just return it directly

        #   This makes root namespace at '/' persistent because:
        #   Pobiverse.__init__ has
        #   ```
        #       PV.rootns = PobNS(PV.rootobj, abspath='/')
        #       PV.rootpn = PobNode('/', obj=self.rootns)
        #   ```
        #   and PobNode eval_PYEXPR has
        #   ```
        #       local_ns = dirops.PobNS(self.obj, lazy=False)
        #   ```


        if isinstance(obj, cls):
            # If initialized with obj that's already a PobNS, just return it
            obj._ensure_initialized()  # hmm what does this do with _deltas?
            return obj

        # Otherwise, create a new instance
        return super().__new__(cls)


    def __init__(self, obj, lazy=True, pyonly=False, abspath=None):
        """
        Args:
            obj: Python object from which the namespace is derived
            lazy: If True don't initialize namespace dict until its accessed
            pyonly: If True exclude members derived from object contents (namespace has no contentkeys)
            abspath: absolute pobshell path
        """
        # If the object is already a PobNS, do nothing because we "returned" that object in __new__.
        if isinstance(obj, PobNS):
            return
        self._obj = obj
        self._abspath = abspath
        self._pyonly = pyonly

        self._dict = None      # namespace keys & values from members of obj
        self._deltas = {}      # track changes to PobNS namespace, to persist them across map changes
        self._map = None  # string of map settings at time namespace was populated
        if not lazy:
            self.initialize_namespace()


    def _ensure_initialized(self):
        """Initialize the dictionary only when accessed."""
        # Initialize namespace dict if not already done
        # Or re-initialize if dict was populated with different map setting than current setting
        if self._dict is None or self._map != PobPrefs.map_repr():
            self.initialize_namespace()


    def initialize_namespace(self):
        # Required root parameter from PobNS(PV.rootobj...)
        #   is assigned to self._obj and can be any Python Object
        # Frames get special treatment
        if inspect.isframe(self._obj) and PobPrefs.simpleframes:
            namespace = frame_vars(self._obj)
        else:
            namespace = dict(get_members(self._obj, pyonly=self._pyonly))

        # Remove Pobshell objects from namespace
        if self._abspath == '/':
            for k, v in namespace.copy().items():  # Don't chop the branch we're standing on
                if id(v) in PobPrefs.introspection_ids:
                    del namespace[k]

        namespace.update(self._deltas)
        self._dict = namespace
        self._map = PobPrefs.map_repr()


    def __getitem__(self, key):
        self._ensure_initialized()
        return self._dict[key]

    def __setitem__(self, key, value):
        self._ensure_initialized()
        self._deltas[key] = value
        self._dict[key] = value

    def __delitem__(self, key):
        self._ensure_initialized()
        try:
            del self._deltas[key]
        except KeyError:
            pass
        del self._dict[key]

    def __contains__(self, key):
        self._ensure_initialized()
        return key in self._dict

    def __iter__(self):
        self._ensure_initialized()
        return iter(self._dict)

    def __len__(self):
        self._ensure_initialized()
        return len(self._dict)

    def get(self, key, default=None):
        self._ensure_initialized()
        return self._dict.get(key, default)

    def keys(self):
        self._ensure_initialized()
        return self._dict.keys()

    def values(self):
        self._ensure_initialized()
        return self._dict.values()

    def items(self, pyonly=False):
        self._ensure_initialized()
        if pyonly:
            return [(k, v) for k, v in self._dict.items() if type(k) is str and k.isidentifier()]
        else:
            return self._dict.items()

    def pop(self, key, default=None):
        self._ensure_initialized()
        return self._dict.pop(key, default)

    def clear(self):
        self._ensure_initialized()
        self._dict.clear()

    def update(self, *args, **kwargs):
        self._ensure_initialized()
        self._dict.update(*args, **kwargs)


    def cat(self):
        """Return code listing for self._obj if it is a frame; skipping pdb related frames """

        def first_real_source_frame(frame):
            """Walk back until we hit a non-debug frame whose file exists on disk."""
            def invalid_frame(f):
                return (not os.path.exists(frame.f_code.co_filename)
                        or os.path.basename(frame.f_code.co_filename) in ('pdb.py', 'cmd.py', 'bdb.py'))

            while frame and invalid_frame(frame):
                frame = frame.f_back
            return frame

        def smart_code_context(context=100):
            frame = first_real_source_frame(self._obj)
            if frame is None:
                return NoSuchInfo()
            info = inspect.getframeinfo(frame, context=context)
            if not info:
                return ''
            return ''.join(info.code_context[:info.index+1])

        self._ensure_initialized()
        if not (inspect.isframe(self._obj) and PobPrefs.simpleframes):
            return NoSuchInfo()
        return smart_code_context()


    def copy(self):
        # only used by cmd2._run_python and cmd2.do_ipy
        #   this allows py_locals to be persistent despite
        #   cmd2.do_ipy copying py_locals to avoid persistence
        return self._dict


    def dict_copy(self):
        self._ensure_initialized()
        return self._dict.copy()


    def as_dict(self):
        self._ensure_initialized()
        return self._dict


    @property
    def holds_simple_frame(self):
        self._ensure_initialized()
        return inspect.isframe(self._obj) and 'variables' in self._map


    def setdefault(self, key, default=None):
        self._ensure_initialized()
        return self._dict.setdefault(key, default)

    def __repr__(self):
        if self._abspath == '/':
            return "/"
        if self._dict is not None:
            return "PobNS("+pprint.saferepr(self._dict.items())+")"
            # return f"PobNS({self.items()})"
        return "PobNS(Not initialized)"



class PobException(Exception):
    # Base class for Pobshell Exceptions
    pass


class StopWalking(PobException):
    pass


class PobMissingMemberException(PobException):
    pass


def get_pk_member(obj: object, pkey: str, exception_on_fail=False) -> object:
    # take pkey: a pobkey and return associated member from obj
    #    - a pobkey is a string-valued key, which may be an attribute identifier, or
    #      a string containing a contentkey-delimited repr of a Python expression used as dict key or sequence index

    if pkey.startswith(PobPrefs.contentkey_delimiter) and pkey.endswith(PobPrefs.contentkey_delimiter):
        # pkey is contentkey_delimiter delimited: try literal_eval to convert the repr to an object we can use as a key
        try:
            pkey = literal_eval(pkey[1:-1])
        except (ValueError, SyntaxError):   # contentkey-delimited expression is not a literal expression
            # repr isn't amenable to literal eval
            #   Let's do it the slow way: Iterate over repr of each namespace key, looking for a string that matches key
            for k, v in get_pk_members(obj, exception_on_fail):
                if k == pkey:
                    return v
            if exception_on_fail:
                raise PobMissingMemberException(f"Key '{pkey}' not found in {short(pprint.saferepr(obj), 120)}")
            else:
                return ObjNone

    # pkey now has no contentkey-delimiters and may be any hashable object including a string
    # Retrieve value for pkey
    try:
        return get_member(obj, pkey)
    except (AttributeError, KeyError) as e:
        # appy exception_on_fail logic to PobNS KeyErrors or Generic Python AttributeErrors
        #   TODO What about generic Python KeyErrors?  E.g. bad dict key or list index?
        # otherwise raise the Exception
        if ((isinstance(obj, PobNS) and isinstance(e, KeyError)) or
            (not isinstance(obj, PobNS) and isinstance(e, AttributeError))):
            if exception_on_fail:
                raise PobMissingMemberException(f"Key '{pkey}' not found in {short(pprint.saferepr(obj), 120)}")
            else:
                return ObjNone
        else:
            raise


def get_pk_members(obj: object, exception_on_fail=True, obj_is_Pobiverse=False) -> list:
    # for any object obj, return a list of all the k, v pairs it contains
    #   respecting settings for PobPrefs.static, PP.contents and PP.mro
    #   each k is a string-valued key
    #       (may be a string containing a contentkey-delimited repr of hashable dict key or list index
    #   each v is the associated value from obj.k or obj[k]

    try:
        if obj_is_Pobiverse:
            # - PobNS is root py_namespace so already contains (pobkey, value) pairs
            #   which we can retrieve with its .items method
            # - Pobiverse has its own special .items method that excludes py_locals to prevent recursion crash
            #   when pobshell browses itself
            return list(obj.items())

        return [(to_pobkey(k), v) for k, v in get_members(obj)]
    except (KeyboardInterrupt, RecursionError):
        raise
    except Exception as e:
        if exception_on_fail:
            raise PobException(f"Exception {e}:: Cannot retrieve keys from {obj}")
        else:
            return []


def to_pobkey(akey: object) -> str:
    # convert any Python container key (e.g. dict key) or Sequence index (e.g. list index) to a pobkey
    #   * pobkeys are keys to PobNamespaces
    #   * PobNamespaces are dict like objects that combine Python namespaces and containers,
    #       so pobkeys have to represent
    #       -  attribute name strings
    #       -  dict keys that can be any hashable object, e.g. a named tuple or an integer
    # if akey is a valid Python identifier it is return unchanged, e.g. "foo"
    # - other objects are converted to a contentkey: the repr of the object, wrapped in contentkey-delimiters
    #      e.g.
    #      "`Point(x=42, y=42)`" (a named tuple key),
    #      "`42`" (an integer key),
    #      "`'email._parseaddr'`" (a module used as a key in sys.modules)

    # NB must be idempotent, ie to_pobkey(to_pobkey(x)) must equal to_pobkey(x)

    # return akey unchanged if its a valid identifier
    if isinstance(akey, str) and akey.isidentifier():
        return akey
    # return unchanged if object is a string containing a contentkey-delimited expression
    elif (isinstance(akey, str) and akey.startswith(PobPrefs.contentkey_delimiter)
          and akey.endswith(PobPrefs.contentkey_delimiter)):   # 2 Feb 2025
        # elif isinstance(akey, str) and akey.startswith(PobPrefs.contentkey_delimiter):
        return akey
    else:
        # return a contentkey-delimited repr of the object
        return PobPrefs.contentkey_delimiter + xtra_safe_repr(akey) + PobPrefs.contentkey_delimiter



def eval_key_maybe(skey: str) -> object:
    # return python-eval of a contentkey-delimited path component, return others (string type keys) unchanged
    # skey: a path component, possibly contentkey-delimited
    if skey.startswith(PobPrefs.contentkey_delimiter) and skey.endswith(PobPrefs.contentkey_delimiter):
        try:
            return literal_eval(skey[1:-1])  # TODO maybe eval in rootns
        except (ValueError, SyntaxError):
            return skey
    else:
        return skey


def explode_pobkey_path(pk_path: str):
    # take a '/' delimited path of pobkeys and return them as a list
    assert pk_path.startswith('/')
    return strpath.split_path_all(pk_path)[1:]  # item 0 is always ''


def obj_list_from_abspath(abspath: str, root_obj):
    # return list of Python objects for the object sequence specified by path string from root_obj
    #   root_obj will be rootns
    #   abspath: a normed absolute string path starting from root, '/'
    #       each path component is a pobkey: a valid python identifier or contentkey 
    #   Iterates over the abspath components
    #       First key retrieves Python object from root namespace
    #       Second key retrieves Python object from previous Python object
    #       .. etc

    obj_list = [root_obj]

    if abspath == '/':
        return obj_list

    # make a list of path components
    name_list = explode_pobkey_path(abspath)

    # iterate over the pobkeys, retrieving each Python object from the namespace of the one before
    while len(name_list) > 0:
        obj_list.append(get_pk_member(obj_list[-1], name_list[0], exception_on_fail=True))
        name_list.pop(0)
    return obj_list


def pypath_from_obj_list(abspath: str, objpath: list):
    # return "Python path" with "." and "[]" delimiters
    # i.e. the Python expression specified by abspath and obj_list
    #   abspath: an absolute pob path, which may contain contentkey-delimited components
    #   objpath: a sequence of objects corresponding to abspath

    assert abspath.startswith('/') and isinstance(objpath[0], PobNS)

    if abspath == '/':
        return ''

    name_list = strpath.split_path_all(abspath)[1:]  # path component [0] is empty str
    obj_list = objpath[:]  # NB make a copy so we can pop without mutating original

    if not objpath[0].holds_simple_frame:
        # we need a retrieval expression from root object too
        name_list.insert(0, "ROOT")
    else:
        # treat root as a namespace requiring no retrieval expression
        obj_list = obj_list[1:]

    qualpath = eval_key_maybe(name_list.pop(0))

    while len(name_list) > 0:
        try:
            qualpath += get_retrieval_expr(obj_list.pop(0), eval_key_maybe(name_list.pop(0)))
        except PobMissingMemberException:
            raise

    if not objpath[0].holds_simple_frame:
        return qualpath[4:]
    return qualpath


def getmembers_static(obj, predicate=None, from_mro=True):  # _getmembers tweaked to handle from_mro=False
    """Retrieve all members of an object including instance attributes
    if from_mro is True, include attributes from object's class and the class's mro
    without triggering dynamic lookup (__getattr__, __getattribute__, or __dir__).
    """
    results = []
    processed = set()

    if inspect.isclass(obj):
        mro = inspect.getmro(obj) if from_mro else ()
        names = set(obj.__dict__)  # Class-level attributes
    else:
        if from_mro:
            mro = inspect.getmro(type(obj))
            names = set(type(obj).__dict__)  # Class attributes
        else:
            mro = ()
            names = set()

        if hasattr(obj, '__dict__'):
            names.update(obj.__dict__)  # Include instance attributes

    # Add inherited attributes from base classes
    for base in mro:
        names.update(base.__dict__)

    # Process each name
    for key in names:
        value = None
        found = False

        # Try to retrieve statically (avoids __getattr__)
        try:
            value = inspect.getattr_static(obj, key)
            found = True
        except AttributeError:
            pass  # Fall back to searching in __dict__

        # If getattr_static failed, check instance dict and class dict
        if not found:
            if hasattr(obj, '__dict__') and key in obj.__dict__:
                value = obj.__dict__[key]
                found = True
            else:
                for base in mro:
                    if key in base.__dict__:
                        value = base.__dict__[key]
                        found = True
                        break  # Stop at first occurrence in MRO

        if found and isinstance(value, types.DynamicClassAttribute):
            try:
                # Ensure we get the instance-level value
                value = getattr(obj, key)
            except AttributeError:
                continue  # Skip if inaccessible at the instance level

        if found and (not predicate or predicate(value)):
            results.append((key, value))
            processed.add(key)

    results.sort(key=lambda pair: pair[0])  # Sort results alphabetically
    return results



def get_member(obj, pykey) -> object:
    # retrieve entry for pykey (an attribute name or hashable content key) from object obj;
    # flexing retrieval by PobPrefs.contents and PobPrefs.static
    # NB raise an exception if asked to retrieve an invalid key

    # CONTENTS
    # if we're mapping contents they take priority: first try to retrieve content for key pykey from collection object obj

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        if isinstance(obj, PobNS):
            return obj[pykey]

        if PobPrefs.contents:
            try:
                return obj[pykey]
            except TypeError:
                if isinstance(obj, collections.abc.Set) and pykey in obj:   # treat a set as a dict with values equal to its keys
                    return pykey
                # else pass
            except (IndexError, KeyError):  # object may not be subscriptable, or may not contain this key
                pass

        # ATTRIBUTES
        # pykey didn't refer to content, so try it as an attribute: retrieve value of attribute pykey from object obj
        if not PobPrefs.attributes:
            raise PobMissingMemberException(f"Key '{pykey}' not found in {short(pprint.saferepr(obj), 120)}")

        try:
            if PobPrefs.static:
                return pob_inspect.getattr_static_dict(obj, local=not PobPrefs.mro)[pykey]
            else:
                return getattr_dynamic_py(obj, pykey)
        except (AttributeError, TypeError, KeyError):

            if PobPrefs.auto_import and inspect.ismodule(obj) and hasattr(obj, '__path__'):
                submodules = dict(list_submodules(obj, seen=None))
                try:
                    return submodules[pykey]
                except KeyError:
                    pass
            raise PobMissingMemberException(f"Key '{pykey}' not found in {short(pprint.saferepr(obj), 120)}")



def itemsview(o):
    """return .items() for mapping or set objects """
    if isinstance(o, collections.abc.Mapping):
        return o.items()
    elif isinstance(o, collections.abc.Set):
        return {k: k for k in o}.items()   # treat a set as a dict with values equal to keys


def get_members(obj: object, pyonly=False) -> list[(object, object)]:
    # return a list of (obkey, value) pairs for python object; flexing retrieval by settings in PobPrefs.contents and PobPrefs.static
    #   where obkey is an arbitrary key; string, int, or any immutable object
    #   NB suppresses exceptions when retrieving individual attributes; such attributes are skipped
    # CHECK: handles contents True ✓ & False ✓; static True ✓ & False ✓; mro True ✓ & False ✓


    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        if isinstance(obj, PobNS):
            return obj.items()

        # CONTENTS -------------------------------
        content_keys = set()
        content_items = []

        # if contents setting is True, prioritise collection contents over attributes having same name
        if PobPrefs.contents and not pyonly:
            try:
                if len(obj) > 0:    # skip objects with weird len methods such as sys.modules['numpy.lib.index_tricks'].c_
                    for n, (k, v) in enumerate(itemsview(obj)):   # works for dicts
                        if n == PobPrefs.contents_limit:    # if item_limit is 0, don't process any
                            break
                        content_items.extend([(k,v)])
                        content_keys.add(k)  # track the keys in a set, so we can avoid duplicates when we add keys for attributes

            except (AttributeError, TypeError):  # Object doesn't have items method
                # Maybe object is a sequence, if so retrieve enumerated contents
                # "Sequences represent finite ordered sets indexed by non-negative numbers"
                #   https://docs.python.org/3/reference/datamodel.html
                try:
                    if len(obj) > 0 and isinstance(obj, collections.abc.Iterable): # hasattr(obj, '__getitem__')   # then its a sequence
                        _ = obj[0]    # raise an exception to skip enumerating this object if it isn't iterable from 0
                        for n, v in enumerate(obj):  # works for lists and tuples like things
                            if n == PobPrefs.contents_limit:   # if item_limit is 0, don't process any
                                break
                            content_items.extend([(n, v)])

                except KeyboardInterrupt:
                    raise
                except:  # other than ^C, we don't care what kind of exception; just means this isn't a simple sequence
                    pass

        # ATTRIBUTES -------------------------------
        #   NB We skip the attribute in case of duplicate keys where an attribute matches a content key
        #       e.g. this is common with sklearn.bunch

        # - Filter out any None values returned - safe_getattr_item returned None for keys that aren't found
        # - Add the remainder to any items we got from collection contents:
        if not PobPrefs.attributes:
            items = []
        else:
            # TODO: Should contents or attributes take priority when a key/name is in both?
            #   Currently, contents have priority
            if PobPrefs.static:
                # CHECK: static True ✓;  mro True ✓ & False ✓
                # items = [(k, v) for k, v in pob_inspect.getattr_static_dict(obj, local=not PobPrefs.mro).items()
                #                                        if k not in content_keys]
                #  TODO Why is this sorted and static False not sorted ?
                #  I'll leave it sorted ..  Chesterton's fence
                items = sorted([(k, v) for k, v in pob_inspect.getattr_static_dict(obj, local=not PobPrefs.mro).items()
                                                       if k not in content_keys], key=lambda x: x[0])
            else:
                # getmembers_py flexes by PobPrefs.mro
                # CHECK: static False ✓; mro True ✓ & False ✓
                items = [(k, v) for k, v in getmembers_py(obj) if k not in content_keys]
                # items = sorted([(k, v) for k, v in getmembers_py(obj) if k not in content_keys], key=lambda x: x[0]))

        # Design decision:  List attributes before contents - there may be many contents, but usually few attributes
        items.extend(content_items)
        keys = {k for k, _ in items}

        # SUBMODULES -------------------------------
        if PobPrefs.auto_import and inspect.ismodule(obj) and hasattr(obj, '__path__'):
            items.extend(list_submodules(obj, seen=keys))

    return items


def list_submodules(
        package,
        seen: Optional[set] = None
) -> List[Tuple[str, object]]:
    """
    List only the immediate (one-level) submodules of the given package.

    It uses pkgutil.walk_packages but filters out deeper modules
    by checking for additional dots in the fully qualified module name.
    This prevents calling importlib.import_module on deeper levels
    that won't be surfaced anyway, thus avoiding unnecessary imports.

    Returns:
        A list of (local_name, imported_module_object) for each discovered
        immediate child submodule (or subpackage).
    """
    if seen is None:
        seen = set()

    # You mentioned redirecting stderr to suppress autoimport warnings.
    # Adjust as needed for your environment:
    # context = redirect_stderr(...)  # e.g. redirect_stderr(StdSim(io.StringIO()))
    context = redirect_stderr(StdSim(io.StringIO()))  # Don't report errors due to autoimport

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with context:
            module_list = []

            # pkgutil.walk_packages will still 'find' deeper modules, but we'll skip them below.
            for loader, module_name, is_pkg in pkgutil.walk_packages(
                    package.__path__,
                    package.__name__ + '.'  # e.g. "mypackage."
            ):
                # Strip off the package prefix ("mypackage.") to get just the local part
                local_name = module_name[len(package.__name__) + 1:]

                # If there's still a dot in local_name, it's a deeper module (e.g. "sub1.sub2"), skip it
                if '.' in local_name:
                    continue

                # Skip any submodule already seen
                if local_name in seen:
                    continue
                seen.add(local_name)

                # Don't import __main__
                if local_name == '__main__':
                    continue

                # Only import if:
                #   - It's a package, OR
                #   - user prefs say auto-import modules
                if PobPrefs.auto_import:  # or is_pkg:
                    try:
                        imported_module = importlib.import_module(module_name)
                        module_list.append((local_name, imported_module))
                    except KeyboardInterrupt:
                        raise
                    except Exception:
                        # It's not worth reporting exceptions for failed imports
                        pass

    return module_list


def get_retrieval_expr(o, k) -> str:
    # return a str containing the python expression to retrieve value for key k from object o, flexed as k is attribute or content

    # CONTENTS
    # if we're mapping contents, they take priority: first see if k represents content in a collection object
    # An exception will be raised if k isn't a key for o, or o isn't a collection
    if isinstance(o, PobNS) and not o.holds_simple_frame:
        o = o._obj

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        if PobPrefs.contents:
            try:
                _ = o[k]
                return "[" + repr(k) + "]"
            except KeyboardInterrupt:
                raise
            except TypeError:
                if isinstance(o, set) and k in o:
                    return '.#'+repr(k)  # there is no python expression to return a key from a given set except by enumeration
                # else pass and try the attributes
            except (IndexError, KeyError, ValueError):
                pass

        # ATTRIBUTES
        # k wasn't a key for o, so instead try to retrieve k as an attribute
        try:
            if PobPrefs.static:
                _ = inspect.getattr_static(o, k)
                return "." + str(k)
            else:
                _ = getattr(o, k)
                return "." + str(k)
        except KeyboardInterrupt:
            raise
        except :  # k isn't an attribute so k is invalid, or is a python expression that literal eval couldn't handle
            # get_pk_member iterates over repr of keys of o looking for a string match of repr of k
            try:
                if get_pk_member(o, k) is not ObjNone:
                    sk = str(k)
                    # may need to strip contentkey delimiters from pob key to get a python expression from it
                    if sk.startswith(PobPrefs.contentkey_delimiter):
                        assert sk.endswith(PobPrefs.contentkey_delimiter)
                        sk = sk[1:-1]
                    return "[" + sk + "]"
                else:
                    raise PobMissingMemberException(f"Key '{k}' not found in {o}")
            except PobMissingMemberException:
                if k.startswith(PobPrefs.contentkey_delimiter) and k.endswith(PobPrefs.contentkey_delimiter):
                    return "[" + k[1:-1] + "]"
                else:
                    return "." + str(k)  # Can't retrieve k from o, maybe the map isn't valid; go with default retrieval


# def getattr_static_py(o, k):
#     # map static, mro OR local
#     # wrap inspect.getattr_static so it transforms most Exceptions into NoSuchInfo objects
#     #  inspect._getmembers chokes on all attributes for an object if any attribute
#     #   raises an Exception that isn't AttributeError  E.g. apsw.cursor may show no attributes at all if
#     #   its "description" attribute raises an ExecutionCompleteError exception on retrieval
#     # so this is a wrapper for getattr, that responds to most exceptions by returning a NoSuchInfo object
#
#     # TODO: This does not check the member is valid for current map setting
#     #  Should check PobPrefs.local or PobPrefs.from_mro
#     #      Just returns a static value for the key
#     try:
#         return inspect.getattr_static(o, k)
#     except (AttributeError, KeyboardInterrupt, SystemExit):
#         raise
#     except Exception as e:
#         return NoSuchInfo(str(e))


def getattr_dynamic_py(o, k):
    # wrap builtin getattr to trap some exceptions, returning them as NoSuchInfo Exception objects

    # Supports map dynamic, mro, or local

    # like standard getattr, but converts weird retrieval exceptions to AttributeErrors for consistent handling
    #   E.g. apsw.cursor's "description" attribute may raise an ExecutionCompleteError exception on retrieval

    try:
        if PobPrefs.mro:
            # N.B. getattr(o, k) doesn't retrieve abstract base class attributes, e.g. /Cafe/__class__/__annotations__
            #   despite get_members() returning (k, v) pairs that include them
            return getattr(o, k)
        else:
            return vars(o)[k]
    except (AttributeError, KeyError, KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:
        raise AttributeError(str(e))


# TODO: Rename the function below.
#   It's only designed for members that are python attributes.
#   and it's dynamic only - it uses dir() or obj.__dir__.keys()
#   but it does flex by PP.mro
#   ...
#   so the name should be get_attributes_dynamic(obj,

def getmembers_py(obj, predicate=None):
    """ Return map flexed list of (name, value) tuples for obj's members.  If name is given, just that pair

    #  only used with PP.static False

    Args:
        obj: object whose members are required
        predicate: inspect.is* function for filtering returned values

    Returns:

    """
    # This function is dynamic only because it relies on dir(obj) for non-local retrieval
    # But it flexes by "map mro" or "map local" as required
    if PobPrefs.mro:
        names = dir(obj)
    else:
        names = list(obj.__dict__.keys()) if hasattr(obj, '__dict__') else []

    if isclass(obj):
        if not PobPrefs.mro:
            mro = ()
        else:
            mro = getmro(obj)
            # add any DynamicClassAttributes to the list of names if obj is a class;
            # this may result in duplicate entries if, for example, a virtual
            # attribute with the same name as a DynamicClassAttribute exists
            try:
                for base in obj.__bases__:
                    for k, v in base.__dict__.items():
                        if isinstance(v, types.DynamicClassAttribute):
                            names.append(k)
            except AttributeError:
                pass
    else:
        mro = ()

    results = []
    processed = set()

    for key in names:
        # First try to get the value via getattr.  Some descriptors don't
        # like calling their __get__ (see bug #1785), so fall back to
        # looking in the __dict__.
        try:
            value = getattr_dynamic_py(obj, key)
            # handle the duplicate key
            if key in processed:
                raise AttributeError
        except AttributeError:
            for base in mro:
                if key in base.__dict__:
                    value = base.__dict__[key]
                    break
            else:
                # could be a (currently) missing slot member, or a buggy
                # __dir__; discard and move on
                continue
        if not predicate or predicate(value):
            results.append((key, value))
        processed.add(key)
    results.sort(key=lambda pair: pair[0])
    return results
