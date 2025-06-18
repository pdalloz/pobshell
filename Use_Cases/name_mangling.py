class Parent:
    def __init__(self):
        self.__private_attr = "Parent's private attribute"

class Child(Parent):
    def __init__(self):
        super().__init__()
        self.__private_attr = "Child's private attribute"

obj = Child()
# The two private attributes do not conflict due to name mangling
print(obj._Parent__private_attr)  # Access parent attribute
print(obj._Child__private_attr)  # Access child attribute
import pobshell; pobshell.shell()
