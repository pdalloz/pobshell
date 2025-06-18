class MyClass:
    class_attr = "I am a class attribute"

    def __init__(self):
        self.instance_attr = "I am an instance attribute"

obj = MyClass()
print(obj.__dict__)  # {'instance_attr': 'I am an instance attribute'}
import pobshell; pobshell.shell()
