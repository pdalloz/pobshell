import collections

# example code for testing and debugging

short_list = ['abiflags', 'addaudithook', 'api_version', 'argv']
long_list = ['x'*i for i in list(range(0, 20))]
my_global_str = "Now is the time for all good men to come to the aid"
the_walrus_and_the_carpenter_were_walking_close_at_hand = ("They'd eaten every one.", 64)
my_global_dict = {"foo ooo": [1, 2, 3], "bar": [[4.0], [5.0], [6.0]], '(': ')', '[': ']',
                  'foo2': ['a', 'b', 'c'], 'foo3': ['a', 'b'], 3: 'three', 33: 'thirty three', 'rien': None,
                  the_walrus_and_the_carpenter_were_walking_close_at_hand: "The time has come,' the Walrus said, To talk of many things"}
rien_de_rien = None


Card = collections.namedtuple('Card', ['rank', 'suit'])

class FrenchDeck:
    ranks = [str(n) for n in range(2, 11)] + list('JQKA')
    suits = 'spades diamonds clubs hearts'.split()

    def __init__(self):
        self._cards = [Card(rank, suit) for suit in self.suits
                                        for rank in self.ranks]

    def __len__(self):
        return len(self._cards)

    def __getitem__(self, position):
        return self._cards[position]




# from cmd2 import columnize

import pathlib
import os

# from memory_profiler import profile
from random import randint

# https://realpython.com/python-descriptors/
class VerboseAttribute:
    def __get__(self, obj, type=None) -> object:
        print("VerboseAttribute: Getting the attribute value")
        return 42, randint(1, 100000)
    def __set__(self, obj, value) -> None:
        print("VerboseAttribute:Setting the attribute value")
        raise AttributeError("Value is locked: Cannot change the attribute value")

class Foo:
    attribute1 = VerboseAttribute()
    alpha = 0.00729735253
    simple_str = 'Hello world'

    def __init__(self):
        self.e = 2.718281828459045



# p = Pobiverse.Pobiverse('', 'find sin')
# p = Pobiverse.Pobiverse('', 'find argparse')
def function1(my_param:str):
    print(f'Received a {my_param}')
    my_foo_instance = Foo()
    x = my_foo_instance.attribute1
    print(x)
    # pob.shell()
    print('done')


# @profile
def do_stuff():
    """
    A function for doing stuff
    """
    s = 'the quick brown fox jumps over the lazy dog'
    codes = {'a': 1, 'b': 2, 'c': 3}
    reverse_codes = {26: 'z', 25: 'y', 24: 'x', 99: function1}
    print('about to start executing function1 ')
    function1('Stringy Parameter')
    print('just finished executing function1')


class Ten:
    def __get__(self, obj, objtype=None):
        return 10

class A:
    x = 5                       # Regular class attribute
    y = Ten()                   # Descriptor instance

# if __name__ == '__main__':
a = A()
# p.cmdloop()
do_stuff()

beer_card = Card('7', 'diamonds')
deck = FrenchDeck()


def main():
    from pprint import pformat
    sfsfkjsfksjk = pformat(long_list, compact=True, sort_dicts=True)
    print(sfsfkjsfksjk)
    

    import pobshell
    pobshell.shell(persistent_history_file=None)
    print('Finishing main')


if __name__ == '__main__':
    main()    

