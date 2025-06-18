"""
Pobkey-aware string operations on Posix style paths

Path operations on paths where some components may not be valid identifiers,
but instead contentkey-delimited reprs of Python objects, e.g. `1729` or `("spam", 42)`

Largely adapted from Lib/posixpath.py
"""

# Strings representing various path-related bits and pieces.
# These are primarily for export; internally, they are hardcoded.
# Should be set before imports for resolving cyclic dependency.

from .common import PobPrefs
SEP = '/'


def blanked_contentkeys(spath):
    # replace contentkey-delimited elements of abspath by X's, so splitting on '/' will exclude contentkey_delimiter-escaped substrings
    if PobPrefs.contentkey_delimiter not in spath:
        return spath
    ticksplit = spath.split(PobPrefs.contentkey_delimiter)
    for i in range(1, len(ticksplit), 2):
        ticksplit[i] = "X"*len(ticksplit[i])
    return PobPrefs.contentkey_delimiter.join(ticksplit)


def split_path_all(spath):
    """Contentkey-delimiter-aware path split"""
    if PobPrefs.contentkey_delimiter not in spath:
        return spath.split(SEP)

    spath_blanked = blanked_contentkeys(spath)
    list_blankedpath = spath_blanked.split(SEP)

    listpath = []
    starti = 0
    for i, pathpart in enumerate(list_blankedpath):
        listpath.append(spath[starti:starti+len(pathpart)])
        starti += len(pathpart)+1  # +1 for the '/' char

    return listpath


def isdir(s):
    """For use by Pobiverse.ns_path_completer"""
    return s[-1] == SEP

# Return whether a path is absolute.
# Trivial in Posix, harder on the Mac or MS-DOS.

def isabs(s):
    """Test whether a path is absolute"""
    # s = os.fspath(s)
    return s.startswith(SEP)


# Join pathnames.
# Ignore the previous parts if a part is absolute.
# Insert a '/' unless the first part is empty or already ends in '/'.

def join(a, *p):
    """Join two or more pathname components, inserting '/' as needed.
    If any component is an absolute path, all previous path components
    will be discarded.  An empty last part will result in a path that
    ends with a separator."""
    path = a
    try:
        if not p:
            return path[:0] + SEP  # 23780: Ensure compatible data type even if p is null.
        for b in p:
            if b.startswith(SEP):
                path = b
            elif not path or path.endswith(SEP):
                path += b
            else:
                path += SEP + b
    except (KeyboardInterrupt, TypeError, AttributeError, BytesWarning):
        # genericpath._check_arg_types('join', a, *p)
        raise
    return path


# Split a path in head (everything up to the last '/') and tail (the
# rest).  If the path ends in '/', tail will be empty.  If there is no
# '/' in the path, head  will be empty.
# Trailing '/'es are stripped from head unless it is the root.

def split(spath):
    """Split a pathname.  Returns tuple "(head, tail)" where "tail" is
    everything after the final slash.  Either part may be empty."""
    # blank the contentkey_delimiter escaped sequences before searching for SEP, then use index for found-SEP in original abspath
    if not spath:
        return ('','')
    spath_blanked = blanked_contentkeys(spath)
    i = spath_blanked.rfind(SEP) + 1
    head, tail = spath[:i], spath[i:]
    if head and head != SEP*len(head):
        head = head.rstrip(SEP)
    return head, tail


# Return the last part of a path, same as split(path)[1].
def basename(spath):
    """Returns the last component of a pathname"""
    # blank the contentkey_delimiter escaped sequences before searching for SEP, then use index for found-SEP in original abspath
    spath_blanked = blanked_contentkeys(spath)
    i = spath_blanked.rfind(SEP) + 1
    return spath[i:]


# Return the head (dirname) part of a path, same as split(path)[0].

def dirname(spath):
    """Returns the directory component of a pathname"""
    # blank the contentkey_delimiter escaped sequences before searching for SEP, then use index for found-SEP in original abspath
    spath_blanked = blanked_contentkeys(spath)
    i = spath_blanked.rfind(SEP) + 1
    head = spath[:i]
    if head and head != SEP*len(head):
        head = head.rstrip(SEP)
    return head



# Normalize a path, e.g. A//B, A/./B and A/foo/../B all become A/B.
# It should be understood that this may change the meaning of the path
# if it contains symbolic links!

def normpath(spath):
    """Normalize stringlike path, eliminating double slashes, etc."""
    sep = '/'
    empty = ''
    dot = '.'
    dotdot = '..'
    if spath == empty:
        return dot
    initial_slashes = spath.startswith(sep)
    # POSIX allows one or two initial slashes, but treats three or more
    # as single slash.
    if (initial_slashes and
        spath.startswith(sep*2) and not spath.startswith(sep*3)):
        initial_slashes = 2
    comps = split_path_all(spath)
    new_comps = []
    for comp in comps:
        if comp in (empty, dot):
            continue
        if (comp != dotdot or (not initial_slashes and not new_comps) or
             (new_comps and new_comps[-1] == dotdot)):
            new_comps.append(comp)
        elif new_comps:
            new_comps.pop()
    comps = new_comps
    spath = sep.join(comps)
    if initial_slashes:
        spath = sep*initial_slashes + spath
    return spath or dot


def abspath(path, cwd=None):
    """
    Return an absolute path.

    NB No trailing /
    """
    if not isabs(path):
        assert cwd is not None
        path = join(cwd, path)
    return normpath(path)

