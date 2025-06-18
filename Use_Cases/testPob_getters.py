
# Test Cases

import random
# Standard Python class ----------------------------
print("Standard Python class ----------------------------")
class StandardClass:
    def __init__(self):
        self.x = 10
        self.y = 20

objStC = StandardClass()
objStC.z = 30  # Dynamically added attribute

print("local & static(obj1): EXPECT x, y, z")   # ✓
print("     local & static(StandardClass): __init__  & generic class dunders")

# slots --------------------------------------------
print("slots --------------------------------------------")
# __slots__ class
class SlotClass:
    __slots__ = ['a', 'b']
    def __init__(self):
        self.a = 1
        self.b = 2

objSlC = SlotClass()
objSlC.a = 42  # Updating slot attribute

print("local & static(obj2): EXPECT __slots__  (?)")
print("     local & static(SlotClass): EXPECT __slots__, __init__, [other dunders?] ")




# Bunch instance ----------------------------------------
print("Bunch instance ----------------------------------------")
print("  Bunch does have instance attributes, but they are stored in the dictionary itself.")

from sklearn.utils import Bunch
b = Bunch(a=1, b=2)
b.c = 3  # Adding attribute dynamically
print("     local & static(b): EXPECT None")
print("     local & static(Bunch): EXPECT Bunch methods & generic class dunders")



# ====================================================
# Retrieve instance attributes
# print("Standard Class:", get_instance_attributes(obj1))  # {'x': 10, 'y': 20, 'z': 30}
# print("Slots Class:", get_instance_attributes(obj2))  # {'a': 42, 'b': 2}
# print("Bunch Instance:", get_instance_attributes(b))  # {'a': 1, 'b': 2, 'c': 3}


# Dynamic attributes --------------------------------
print("Dynamic attributes --------------------------------")

print(
"""     __getattr__: Dynamic Attribute Resolution"""
"""     Where is retrieval intercepted?"""
"""     The __getattr__ method is only called when an attribute is missing from __dict__ and __class__."""
"""     It provides a fallback mechanism for missing attributes."""
"""     Example: __getattr__ Injecting Virtual Attributes""")


class DynamicAttr:
    def __getattr__(self, name):
        return f"Generated-{name}"

d = DynamicAttr()
print(f"EXPECT 'Generated-foo': {d.foo=}")  # "Generated-foo"


# Since these attributes do not exist statically, they should not be considered instance attributes
# under our definition.

# local & static(d): None
# local & static(DynamicAttr): __getattr__ & generic class dunders
# For local we should ignore __getattr__ results and only collect attributes stored elsewhere.



# Slots but no dict -----------------------
print("Slots but no dict -----------------------")

class NoDictSlots:
    __slots__ = ['a', 'b']
    def __init__(self):
        self.a = 1
        self.b = 2

objNDS = NoDictSlots()
# I don't think below is correct:

#  if a class defines __slots__, it prevents the instance
#  from having a __dict__, and attributes are instead stored in predefined slot
#  locations.  Access is managed by Python internals, __slots__ specific

# if we're doing static retrieval only then attributes won't
#   magically arrive from class's __slots__ attribute for map static
print("local & static(obj): EXPECT None")
print("local & static(NoDictSlots): EXPECT __slots__ & other class dunders")



# Metaclasses -----------------------------------
print("Metaclasses -----------------------------------")
print("     If an object is an instance of a metaclass")
print("         it may store attributes at the class level, even though it behaves like an instance.")

class Meta(type):
    def __init__(cls, name, bases, dct):
        cls.meta_attr = "I'm in the metaclass"

class MyClassMeta(metaclass=Meta):
    pass

objMCM = MyClassMeta()

# Metaclass attributes are not instance attributes of obj, only of MyClass2.
# static local retrieval should avoid metaclass attributes unless obj is itself a Metaclass


# Metaclass injected attributes --------------------------
print("Metaclass injected attributes -------------------------- ")

class Meta2(type):
    def __getattribute__(cls, name):
        if name == 'injected':
            return "I was injected!"
        return super().__getattribute__(name)

class MyClassMeta2(metaclass=Meta2):
    pass

objMeta2 = MyClassMeta2()
print('Exists, but not in __dict__:', getattr(objMeta2, 'injected', 'injected?Nope'))  # Exists, but not in __dict__
print('injected' in objMeta2.__dict__)  # False


print(" Metaclasses or dynamically modifying __class__ can create behaviors where")
print("     an attribute seems to exist without being stored in __dict__")
print()
print("     injected appears to be an instance attribute but is injected dynamically via metaclass behavior.")


# Another property example ------------------------------
print("Another property example ------------------------------")
print(" Dynamic property generate a new object on each call")
class Example:
    @property
    def new_object(self):
        return random.random()

eExample = Example()


# C extension types ------------------------------
print("C extension types ------------------------------ ")
print("Some C-based objects (like namedtuple, NumPy arrays, and built-in types) ")
print("do not store attributes in __dict__")
print("namedtuple ...")

print("Check if obj lacks __dict__ but has attributes stored elsewhere, like _fields in namedtuple.")
print(" local & static: Empty because x & y are class attributes ?")

from collections import namedtuple
Point = namedtuple("Point", ["x", "y"])
pPoint = Point(1, 2)



# weakref proxies -----------------------------------------------
print(" weakref proxies -----------------------------------------------")
import weakref

class MyClassweakref:
    def __init__(self):
        self.a = 10

objweakref = MyClassweakref()
proxy = weakref.proxy(objweakref)
print(f"Works, but proxy has no direct storage: {proxy.a=}")  # Works, but proxy has no direct storage

print("WeakRef proxies should be excluded since they do not hold attributes directly.")
print("local & static: Empty")

# state change -------------------------------

print("state change -------------------------------")
print("     confirm no state change for property retrieval with map static")
print()
print("     local & static: 'incrementing' should retrieve the method, not a number ")
print("     and _counter should not change")

class Stateful:
    def __init__(self):
        self._counter = 0

    @property
    def incrementing(self):
        self._counter += 1  # Modifies state when accessed!
        return self._counter

objStateful = Stateful()

# just more properties ------------------
print()
print("just more properties ------------------")
class Person:
    def __init__(self, first, last):
        self.first = first
        self.last = last

    @property
    def full_name(self):
        return f"{self.first} {self.last}"  # Dynamically computed

pPerson = Person("John", "Doe")
#  local & static(p):
print(pPerson.full_name)  # Computed dynamically


# __getattr__  again ----------------------
print()
print("__getattr__  again ----------------------")
class VirtualAttrs:
    def __getattr__(self, name):
        return f"Generated value for {name}"

objVA = VirtualAttrs()
print(objVA.some_attr)  # Executes __getattr__

print('some_attr' in objVA.__dict__)  # False (not stored)
# If __getattr__ or __getattribute__ dynamically provides attributes,
#   those attributes behave as if they are on the instance without
#   being stored in __dict__.


# Instance level descriptors --------------------------
print()
print("Instance level descriptors --------------------------")

class Descriptor:
    def __get__(self, instance, owner):
        return "I execute on access!"

class MyClassD2I:
    pass

objMcd2i = MyClassD2I()
objMcd2i.dynamic = Descriptor()  # Descriptor stored in __dict__

print("objMcd2i: Execute __get__ dynamically:", objMcd2i.dynamic)  # Executes __get__ dynamically
print("# {'dynamic': <__main__.Descriptor object>}:", objMcd2i.__dict__)  # {'dynamic': <__main__.Descriptor object>}

# If a descriptor object (e.g., a property or __get__ method) is assigned directly
# to an instance, it executes code but does not necessarily get stored in __dict__.


# NB ====================================================================
print()
print(" ====================================================================")
print("SCENERIO SET: ATTRIBUTE EXISTS OUTSIDE __dict__")
#  An attribute is usually defined on an instance if it appears in instance.__dict__.
#  However, edge cases where an attribute exists but isn't stored in __dict__ include:
#
# __slots__ preventing __dict__ storage
# __getattr__ or __getattribute__ dynamically creating attributes
# __setattr__ redirecting storage
# Instance-level descriptors executing code without being stored normally
# Metaclasses or dynamic __class__ manipulation injecting attributes

# QQ:  In each of those edge cases, is there code assigned somewhere that intercepts normal retrieval?
# 1. __slots__:
#   The class-level __slots__ declaration removes __dict__, and instead, the attribute is stored in a slot in memory, managed internally by Python

print("1: Slots -------------------------------")
class Slotted:
    __slots__ = ('x',)

objSlotted = Slotted()
objSlotted.x = 10  # No __dict__, stored in __slots__
print('objSlotted retrieval via __slots__ from ".x"', objSlotted.x)  # Retrieved via __slots__ mechanism
print('objSlotted hasattr __dict__?:', hasattr(objSlotted, '__dict__'))  # False



# 3. enum.Enum in Python Standard Library
# value is a DynamicClassAttribute, so it only exists on instances, not on the class
print()
print("2: Went walkabout ------------------------------- ")
print()
print("3?: enum.Enum -------------------------------")
from enum import Enum

class Color(Enum):
    RED = 1
    GREEN = 2

print('✓ 1 (allowed):', Color.RED.value)  # ✓ 1 (allowed)
print('✗ AttributeError (not on class!):', getattr(Color, 'value', 'value?Nope'))      # ✗ AttributeError (not on class!)
# Python’s enum.Enum uses DynamicClassAttribute to ensure that name and value
#   only exist on instances, but not on the class

print()
print("TODO  XXX Add the rest of these ")
import pobshell; pobshell.shell()


