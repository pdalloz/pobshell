
from datetime import datetime
print(__name__, '  ', datetime.now())


import pobshell

def get_members(obj, local=True, dynamic=False, contents=False):
    # return the set of names of obj's attributes
    POB = pobshell.pob(root=obj,
                       persistent_history_file=None,
                       map_init=('local' if local else 'mro'),
                       cmd='map -q ' + ('dynamic' if dynamic else 'static'))
    # POB.onecmd_plus_hooks('map -q ' + ('local' if local else 'mro'))
    # POB.onecmd_plus_hooks('map -q ' + ('dynamic' if dynamic else 'static'))
    POB.onecmd_plus_hooks('map -q ' + ('contents' if contents else 'attributes'))
    return set(pn.name for pn in POB.curr_path.all_child_paths())



def get_member(obj, pobkey, local=True, dynamic=False, contents=False):
    # return the value of obj's attribute whose name is pobkey (may be backticked)
    POB = pobshell.pob(root=obj,
                       persistent_history_file=None,
                       cmd=f"""map -q {'local' if local else 'mro'}; map -q  {'dynamic' if dynamic else 'static'} """)
    # POB.onecmd_plus_hooks('map -q ' + ('local' if local else 'mro'))
    # POB.onecmd_plus_hooks('map -q ' + ('dynamic' if dynamic else 'static'))
    POB.onecmd_plus_hooks('map -q ' + ('contents' if contents else 'attributes'))

    POB.onecmd_plus_hooks(f'cd {pobkey}')
    childpn = POB.curr_path
    return childpn.obj


# 1) Standard Python Class
# ---------------------------------------------------
class StandardClass:
    def __init__(self):
        self.x = 10
        self.y = 20

objStC = StandardClass()
objStC.z = 30

# Instance has x, y, z in its __dict__.
# Class does not have x, y, z, but does have __init__, etc.

# INSTANCE (objStC)
assert {'x', 'y', 'z'} <= get_members(objStC, local=True,  dynamic=False)  # assert it's a subset
# assert all(k in get_members(objStC, local=True,  dynamic=False) for k in ['x', 'y', 'z'])

assert {'x', 'y', 'z'} <= get_members(objStC, local=False, dynamic=False)
# assert all(k in get_members(objStC, local=False, dynamic=False) for k in ['x', 'y', 'z'])

# Because dynamic=True typically wouldn’t remove them, they are still present:
assert {'x', 'y', 'z'} <= get_members(objStC, local=True,  dynamic=True)
# assert all(k in get_members(objStC, local=True,  dynamic=True)  for k in ['x', 'y', 'z'])

assert {'x', 'y', 'z'} <= get_members(objStC, local=False, dynamic=True)
# assert all(k in get_members(objStC, local=False, dynamic=True)  for k in ['x', 'y', 'z'])

assert get_member(objStC, 'x', local=False,  dynamic=True) == 10
assert get_member(objStC, 'y', local=True,  dynamic=True) == 20
assert get_member(objStC, 'z', local=True,  dynamic=False) == 30


# CLASS (StandardClass)
assert all(k not in get_members(StandardClass, local=True,  dynamic=False) for k in ['x', 'y', 'z'])
assert all(k not in get_members(StandardClass, local=False, dynamic=False) for k in ['x', 'y', 'z'])
assert all(k not in get_members(StandardClass, local=True,  dynamic=True)  for k in ['x', 'y', 'z'])
assert all(k not in get_members(StandardClass, local=False, dynamic=True)  for k in ['x', 'y', 'z'])

# Class-level methods/dunders are present in the class’s namespace:
assert '__init__' in get_members(StandardClass, local=True, dynamic=False)

# 2) SlotClass with __slots__
# -------------------------------------------------

class SlotClass:
    __slots__ = ['a', 'b']
    def __init__(self):
        self.a = 1
        self.b = 2

objSlC = SlotClass()
objSlC.a = 42

# Instance: a and b exist in slots. There is no instance __dict__,
# but a proper get_members that handles slots should find them if local=True.
# Class: Has __slots__ and __init__ in its dictionary (and all the usual dunders)

# INSTANCE (objSlC)
assert {'a', 'b'} <= get_members(objSlC, local=False, dynamic=False)
# assert 'b' in get_members(objSlC, local=False, dynamic=False)

# CLASS (SlotClass) -- revised version
#  Python inserts descriptors for 'a' and 'b' into the class’s __dict__.
assert {'a', 'b'} <= get_members(SlotClass, local=True,  dynamic=False)
# assert 'b' in get_members(SlotClass, local=True,  dynamic=False)

# We do expect to see the name "__slots__" in the class’s own dictionary if local=True:
assert {'__slots__', '__init__'} <= get_members(SlotClass, local=True,  dynamic=False)
# assert '__init__'   in get_members(SlotClass, local=True,  dynamic=False)


# Should not appear as “a” or “b” on the class level:
# assert 'a' not in get_members(SlotClass, local=True,  dynamic=False)
# assert 'b' not in get_members(SlotClass, local=True,  dynamic=False)
# assert 'a' not in get_members(SlotClass, local=False, dynamic=False)
# assert 'b' not in get_members(SlotClass, local=False, dynamic=False)

# assert '__slots__' in get_members(SlotClass, local=True,  dynamic=False)
# assert '__init__'   in get_members(SlotClass, local=True,  dynamic=False)

# PSD Do we expect to see __slots__ for `map static mro` ?
#    __slots__ vars are retrieved by Python internals code, is this 'dynamic'? is it 'local'?


# 3) Bunch instance
# -------------------------------------------------

from sklearn.utils import Bunch

bnch = Bunch(a=1, b=2)
bnch.c = 3

# The Bunch object typically just uses a normal __dict__ internally. So instance b should have a, b, and c.
#
# Instance: a, b, c.
# Class (Bunch): has the methods of Bunch (e.g. to_dict, update, etc.), but definitely not a, b, or c.

# INSTANCE (b)
# 'a' is stored in content of inherited dict class, so "map contents" should find it on bnch
#   and "contents" ignore map settings for local & dynamic
assert 'a' in get_members(bnch, contents=True, local=False, dynamic=False)
assert 'a' in get_members(bnch, contents=True, local=True, dynamic=False)
assert 'a' in get_members(bnch, contents=True, local=True, dynamic=True)

# but 'a' is also a dynamic attribute  so "map dynamic" should find it on bnch instance
#   - only for "map mro" (local=False) because dir(obj) uses Class __dir__ to return self.keys()
assert 'a' in get_members(bnch, contents=False, local=False, dynamic=True)
#   - with local=True we only look at obj.__dict__ which doesn't have the attribute
assert 'a' not in get_members(bnch, contents=False, local=True, dynamic=True)

# attribute 'c' behaves same way, despite assignment as instance attribute
assert 'c' in get_members(bnch, contents=True, local=False, dynamic=False)
assert 'c' in get_members(bnch, contents=False, local=False, dynamic=True)
assert 'c' not in get_members(bnch, contents=False, local=True, dynamic=True)

# What about Bunch methods, can we see them on instance?
# NO: "map dynamic" uses dir() if from_mro, and dir() returns only the dict keys because of class's __dir__ code
assert '_set_deprecated' not in get_members(bnch, contents=False, local=False,  dynamic=True)
# NO: "map dynamic" uses self.__dict__ if local, so again won't see the Bunch class' methods
assert '_set_deprecated' not in get_members(bnch, contents=False, local=True,  dynamic=True)

#  will "map static" return Class attributes for the instance?
#  if local=True I'd expect not
assert '_set_deprecated' not in get_members(bnch, contents=False, local=False,  dynamic=True)
#  if local=False I'd expect yes
assert '_set_deprecated' in get_members(bnch, contents=False, local=False,  dynamic=False)


# CLASS (Bunch)
assert 'a' not in get_members(Bunch, contents=False, local=True,  dynamic=False)
assert 'a' not in get_members(Bunch, contents=False, local=True,  dynamic=True)
assert 'c' not in get_members(Bunch, contents=True, local=True,  dynamic=True)

# Example check for known Bunch method(s):
assert '_set_deprecated' in get_members(Bunch, contents=False, local=True,  dynamic=False)


# 4) Dynamic attributes via __getattr__
# -------------------------------------------------

class DynamicAttr:
    def __getattr__(self, name):
        return f"Generated-{name}"

d = DynamicAttr()

# Accessing d.foo dynamically returns Generated-foo.
# However, these do not exist in d.__dict__; they are purely virtual.
# Therefore:
#   If local=True, dynamic=False, we do not see 'foo'.
#   If local=True, dynamic=True, depending on your design you might or might not attempt calling __getattr__ for every possible name. (Often that’s impractical, so typically you still do not see 'foo' unless your code enumerates every possible attribute name, which is infinite. Usually we say “virtual attributes do not appear, because they are not physically stored.”)
#   If local=False, we do see __getattr__ as a method on the class, because that is physically in DynamicAttr.__dict__

# INSTANCE (d)
assert 'foo' not in get_members(d, local=True, dynamic=False)
assert 'foo' not in get_members(d, local=True, dynamic=True)   # Usually remains false
# The class method __getattr__ is not stored on d itself:
assert '__getattr__' not in get_members(d, local=True, dynamic=False)

# CLASS (DynamicAttr)
assert '__getattr__' in get_members(DynamicAttr, local=True,  dynamic=False)
assert '__getattr__' in get_members(DynamicAttr, local=False, dynamic=False)
# 'foo' wouldn't appear in the class dictionary either:
assert 'foo' not in get_members(DynamicAttr, local=True, dynamic=False)
assert 'foo' not in get_members(DynamicAttr, local=False, dynamic=False)


# 5) Slots but no __dict__ – NoDictSlots
# -------------------------------------------------

class NoDictSlots:
    __slots__ = ['a', 'b']
    def __init__(self):
        self.a = 1
        self.b = 2

objNDS = NoDictSlots()

# TODO: Del this test? it's near a duplicate of SlotClass above

# INSTANCE (objNDS)
# Instance: a and b exist in slots. There is no instance __dict__
#   so "map static" doesn't find them if local=True
assert 'a' not in get_members(objNDS, local=True,  dynamic=False)
#   but if local=False, "map static" looks at class dict too
assert 'b' in get_members(objNDS, local=False, dynamic=False)

# CLASS (NoDictSlots) -- revised:
assert '__slots__' in get_members(NoDictSlots, local=True, dynamic=False)
assert 'a' in get_members(NoDictSlots, local=True, dynamic=False)
assert 'b' in get_members(NoDictSlots, local=True, dynamic=True)

# CLASS (NoDictSlots)
# assert '__slots__' in get_members(NoDictSlots, local=True, dynamic=False)
# # We do not expect 'a' or 'b' to appear as class-level attributes:
# assert 'a' not in get_members(NoDictSlots, local=True,  dynamic=False)
# assert 'b' not in get_members(NoDictSlots, local=True,  dynamic=False)


# 6) Metaclasses
# 6a) Meta → MyClassMeta
# -------------------------------------------------

class Meta(type):
    def __init__(cls, name, bases, dct):
        cls.meta_attr = "I'm in the metaclass"

class MyClassMeta(metaclass=Meta):
    pass

objMCM = MyClassMeta()

# MyClassMeta has meta_attr on the class, because the metaclass stored it there.
# objMCM does not have meta_attr in its __dict__. Unless local=False, you might see it via normal inheritance from MyClassMeta.
#   But this is a nuance: the class object MyClassMeta itself has meta_attr.
# The metaclass Meta itself might have its own class-level attributes, but that’s an advanced corner.

# INSTANCE (objMCM)
assert 'meta_attr' not in get_members(objMCM, local=True, dynamic=False)
# If local=False, we might see 'meta_attr' because it’s on the class’s dict:
assert 'meta_attr' in get_members(objMCM, local=False, dynamic=False)

# CLASS (MyClassMeta)
assert 'meta_attr' in get_members(MyClassMeta, local=True,  dynamic=False)
assert 'meta_attr' in get_members(MyClassMeta, local=False, dynamic=False)

# 6b) Meta2 → MyClassMeta2
# 6b -------------------------------------------------

class Meta2(type):
    def __getattribute__(cls, name):
        if name == 'injected':
            return "I was injected!"
        return super().__getattribute__(name)

class MyClassMeta2(metaclass=Meta2):
    pass

objMeta2 = MyClassMeta2()

# objMeta2 appears to have an attribute 'injected', but that comes from the metaclass’s __getattribute__.
#   It isn’t in objMeta2.__dict__.
# Similarly, MyClassMeta2.injected also appears to exist,
#   but it is purely dynamic from the metaclass’s __getattribute__

# INSTANCE (objMeta2)
assert 'injected' not in get_members(objMeta2, local=True, dynamic=False)
# Possibly we see it under (local=False, dynamic=True), if your code calls descriptors:
# but typically a dynamic approach would have to try every name. Usually not enumerated.
# So, by default:
assert 'injected' not in get_members(objMeta2, local=False, dynamic=False)

# CLASS (MyClassMeta2)
# Similarly, 'injected' is not physically in MyClassMeta2.__dict__ either.
assert 'injected' not in get_members(MyClassMeta2, local=True, dynamic=False)
assert 'injected' not in get_members(MyClassMeta2, local=False, dynamic=False)

# (If you did implement a fully dynamic approach for get_members(..., dynamic=True),
#   you might see 'injected', but typically that would require enumerating all possible names, which is not standard.
#   So these tests illustrate that it’s not “statically” there.)


# 7) Another property example
# 7 -------------------------------------------------

import random

class Example:
    @property
    def new_object(self):
        return random.random()

eExample = Example()

# new_object is a property in the class dictionary.
# It is not stored in eExample.__dict__.
# If dynamic=True, you might get a value by calling the property, but that changes on each call.
#   For “static” retrieval, we usually skip calling it

# INSTANCE (eExample)
assert 'new_object' not in get_members(eExample, local=True, dynamic=False)
# If local=False, we might see 'new_object' because it’s on the class:
assert 'new_object' in get_members(eExample, local=False, dynamic=False)

# CLASS (Example)
assert 'new_object' in get_members(Example, local=True,  dynamic=False)
assert 'new_object' in get_members(Example, local=False, dynamic=False)


# 8) Namedtuple
# 8 -------------------------------------------------

from collections import namedtuple
Point = namedtuple("Point", ["x", "y"])
pPoint = Point(1, 2)


# pPoint.x and pPoint.y look like instance attributes but are actually stored in a C-level structure.
# pPoint typically has no __dict__.
# Point.x and Point.y are class-level descriptors (or property-like descriptors).


# INSTANCE (pPoint)
# -- revised 14 Feb 2025
# pPoint.__dict__ does not exist (namedtuples are typically immutable, storing fields in C structures).
#   So local=True, dynamic=False for pPoint will yield nothing for 'x' or 'y'.
# Point.__dict__ does contain 'x' and 'y' as property-like descriptors (plus _fields, _field_defaults, etc.).

# The Point class dictionary physically contains 'x' and 'y' descriptors:
assert {'x', 'y'} <= get_members(Point, local=True, dynamic=False)
# assert 'y' in get_members(Point, local=True, dynamic=False)

# For the instance pPoint, it is correct to say 'x' not in get_members(pPoint, local=True, dynamic=False),
#   because there’s no instance __dict__.
assert 'x' not in get_members(pPoint, local=True, dynamic=False)
# If local=False, we see them because they're descriptors on the class:
assert 'y' in get_members(pPoint, local=False, dynamic=False)
# Similarly we see 'x' by normal retrieval, when the map is dynamic and local=False
assert 'x' in get_members(pPoint, local=False, dynamic=True)
# But map dynamic with local=True won't see them because they're not in __dict__
assert 'x' not in get_members(pPoint, local=True, dynamic=True)


# (The exact expectation for namedtuples can vary with your approach.
#   If you consider the namedtuple fields “like slots” and handle them, you could discover them at the instance level.
#   But typically, they’re discovered at the class level as descriptor objects, not in the instance __dict__.)


# 9) Weakref proxies
# 9 -------------------------------------------------

import weakref

class MyClassweakref:
    def __init__(self):
        self.a = 10

objweakref = MyClassweakref()
proxy = weakref.proxy(objweakref)

# proxy acts like objweakref but does not store any attributes itself.
# Usually, “static” inspection of the proxy reveals nothing in its own namespace.

assert 'a' not in get_members(proxy, local=True,  dynamic=False)
assert 'a' not in get_members(proxy, local=False, dynamic=False)

# 10) State change – properties that mutate
# 10 -------------------------------------------------

class Stateful:
    def __init__(self):
        self._counter = 0

    @property
    def incrementing(self):
        self._counter += 1
        return self._counter

objStateful = Stateful()

# If dynamic=False, we do not call incrementing, so it remains a property definition in the class.
# If local=False, that property is discovered on the class, not in the instance dictionary.
# If dynamic=True, you might inadvertently call incrementing, changing _counter

# INSTANCE (objStateful)
# 'incrementing' not in instance’s __dict__:
assert 'incrementing' not in get_members(objStateful, local=True, dynamic=False)
# but if local=False, we see the property on the class
assert 'incrementing' in get_members(objStateful, local=False, dynamic=False)

# CLASS (Stateful)
assert 'incrementing' in get_members(Stateful, local=True,  dynamic=False)
assert 'incrementing' in get_members(Stateful, local=False, dynamic=False)

# 11) Another Person + property
# 11 -------------------------------------------------


class Person:
    def __init__(self, first, last):
        self.first = first
        self.last = last

    @property
    def full_name(self):
        return f"{self.first} {self.last}"

pPerson = Person("John", "Doe")

# first, last in instance dictionary.
# full_name is a property in the class dictionary.

# INSTANCE (pPerson)
assert {'first', 'last'} <= get_members(pPerson, local=True,  dynamic=False)
# assert 'last'  in get_members(pPerson, local=True,  dynamic=False)
assert 'full_name' not in get_members(pPerson, local=True,  dynamic=False)
assert 'full_name' in get_members(pPerson, local=False, dynamic=False)

# CLASS (Person)
assert 'full_name' in get_members(Person, local=True, dynamic=False)


# 12) Another __getattr__ example
# 12 -------------------------------------------------

class VirtualAttrs:
    def __getattr__(self, name):
        return f"Generated value for {name}"

objVA = VirtualAttrs()

# Similar logic to DynamicAttr above. The “some_attr” attribute is not in objVA.__dict__

# INSTANCE (objVA)
assert 'some_attr' not in get_members(objVA, local=True,  dynamic=False)
assert 'some_attr' not in get_members(objVA, local=False, dynamic=False)

# CLASS (VirtualAttrs)
assert '__getattr__' in get_members(VirtualAttrs, local=True, dynamic=False)


# 13) Instance-level descriptors
# 13 -------------------------------------------------

class Descriptor:
    def __get__(self, instance, owner):
        return "I execute on access!"

class MyClassD2I:
    pass

objMcd2i = MyClassD2I()
objMcd2i.dynamic = Descriptor()

# The instance __dict__ has the key 'dynamic' → value is Descriptor() (the descriptor object itself).
# Accessing objMcd2i.dynamic triggers the descriptor’s __get__, returning "I execute on access!"

assert 'dynamic' in get_members(objMcd2i, local=True,  dynamic=False)
assert 'dynamic' in get_members(objMcd2i, local=False, dynamic=False)
# On the class MyClassD2I, "dynamic" is not a class attribute:
assert 'dynamic' not in get_members(MyClassD2I, local=True, dynamic=False)


# 14) Slotted and Enum mention
# 14 -------------------------------------------------

class Slotted:
    __slots__ = ('x',)

objSlotted = Slotted()
objSlotted.x = 10

from enum import Enum

class Color(Enum):
    RED = 1
    GREEN = 2

# The Slotted object is like the other slot examples.
# For Color.RED, the .value and .name are dynamic or descriptor-based. They are not physically on the class Color,
#   so Color.value does not exist.
# (Often, you would do assert 'value' not in get_members(Color, local=True, dynamic=False) and so on.
#   But enumerating all the Enum intricacies can get long.)
assert 'RED' in get_members(Color, local=True,  dynamic=False)
assert 'RED' in get_members(Color, local=True,  dynamic=True)
assert 'GREEN' in get_members(Color, local=False,  dynamic=False)
assert 'GREEN' in get_members(Color, local=False,  dynamic=True)

print('DONE')

# pobshell.shell(persistent_history_file=None)

# TODO:
# '_member_names_' in Color
# '_member_map_' in Color
