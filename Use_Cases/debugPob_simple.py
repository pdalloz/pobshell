
# example code for testing and debugging

data_list = ['abiflags', 'addaudithook', 'api_version', 'argv']
my_global_str = "Now is the time for all good men to come to the aid"

from random import randint

class Foo:
    alpha = 0.00729735253
    simple_str = 'Hello world'

    def __init__(self):
        self.e = 2.718281828459045



def function1(my_param:str):
    print(f'Received a {my_param}')
    my_foo_instance = Foo()    
    x = 27
    # breakpoint()
    import pobshell
    pobshell.shell()
    print('done')


def do_stuff():
    """
    A function for doing stuff
    """
    s = 'the quick brown fox jumps over the lazy dog'
    codes = {'a': 1, 'b': 2, 'c': 3}
    reverse_codes = {26: 'z', 25: 'y', 24: 'x', 99: function1}
    print('start executing function1 ')
    function1('Stringy Parameter')
    print('finished executing function1')


class Ten:
    @property
    def gimme10(self, obj, objtype=None):
        return 10


class A:
    x = 5                       # Regular class attribute
    y = Ten()                   # Descriptor instance

if __name__ == '__main__':
    a = A()
    print(a.y)
    do_stuff()

