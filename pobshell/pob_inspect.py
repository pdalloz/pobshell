"""
Implement getattr_static_dict a Pob version of inspect's getattr_static
which returns a dict of an object's attributes retrieved statically
and supports both 'map local' and 'map mro'
"""

import functools
import types
import weakref

_sentinel = object()
_static_getmro = type.__dict__['__mro__'].__get__
_get_dunder_dict_of_class = type.__dict__["__dict__"].__get__

def _check_instance(obj):
    """
    Return a shallow copy of obj.__dict__ if it exists.
    """
    try:
        return object.__getattribute__(obj, "__dict__").copy()
    except AttributeError:
        return {}

@functools.lru_cache()
def _shadowed_dict_from_weakref_mro_tuple(*weakref_mro):
    """
    Original logic from inspect, unchanged.
    Returns either the overshadowing __dict__ descriptor or _sentinel.
    """
    for weakref_entry in weakref_mro:
        entry = weakref_entry()
        dunder_dict = _get_dunder_dict_of_class(entry)
        if '__dict__' in dunder_dict:
            class_dict = dunder_dict['__dict__']
            if not (type(class_dict) is types.GetSetDescriptorType and
                    class_dict.__name__ == "__dict__" and
                    class_dict.__objclass__ is entry):
                return class_dict
    return _sentinel

def _shadowed_dict(klass):
    """
    Original logic from inspect, unchanged.
    Returns _sentinel if klass's __dict__ is *not* overshadowed.
    """
    return _shadowed_dict_from_weakref_mro_tuple(
        *[weakref.ref(entry) for entry in _static_getmro(klass)]
    )

def _check_class(klass):
    """
    Consolidate all attributes from klass's MRO.
    The MRO is processed in reverse order, so derived classes
    override base classes, matching normal Python attribute resolution.
    """
    consolidated = {}
    for entry in reversed(_static_getmro(klass)):
        # Only update if there's no overshadowing in that part of the MRO
        if _shadowed_dict(type(entry)) is _sentinel:
            consolidated.update(entry.__dict__)
    return consolidated


def getattr_static_dict(obj, local=False):
    """
    Return statically accessible attributes for 'obj' in a single dictionary.

    If local=True:
        Only retrieve attributes physically stored on the object itself:
         - For an instance, that's just obj.__dict__ (if it exists).
         - For a class, that's just obj.__dict__ (if not overshadowed).
         - No MRO or metaclass lookups.

    If local=False:
        (Default) Retrieve attributes via the full static chain:
         - For an instance, merges instance's __dict__ + class + MRO.
         - For a class, merges class + MRO + metaclass MRO.
    """
    if not isinstance(obj, type):
        # obj is an instance
        if local:
            # Only the instance's __dict__
            return _check_instance(obj)
        else:
            # Full chain: instance + reversed MRO
            instance_attrs = _check_instance(obj)
            klass = type(obj)
            class_attrs = _check_class(klass)

            combined = {}
            combined.update(class_attrs)     # base
            combined.update(instance_attrs)  # instance overrides
            return combined

    else:
        # obj is itself a class
        if local:
            # Only the class's own dictionary (ignoring MRO)
            combined = {}
            dict_attr = _shadowed_dict(type(obj))
            if dict_attr is _sentinel:
                combined.update(obj.__dict__)
            return combined
        else:
            # Full chain: class + reversed MRO + metaclass
            klass = obj
            combined = _check_class(klass)
            meta_mro = _static_getmro(type(klass))
            for entry in reversed(meta_mro):
                if _shadowed_dict(type(entry)) is _sentinel:
                    combined.update(entry.__dict__)
            return combined
