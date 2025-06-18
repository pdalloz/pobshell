# -*- coding: utf-8 -*-
"""Various python objects for testing and debugging Pob"""

import collections
import sample_pirate

rien_de_rien = None
α = 1 / 137  # utf8 char

empty_s = ''
tup = (0, empty_s)
d = {'a"': 1, empty_s: 42}

# Some data structures  ======================

short_list = ['dip', 'dip', 'sky', 'blue']
sl_deque = collections.deque(short_list)

menu = ['spam ' * i for i in list(range(1, 12))] + ['eggs']

impossible_things = ["six", "impossible", "things", "breakfast"]
impossible_sort_key = lambda s: "" if s == "breakfast" else s
impossible_things_sorted = sorted(impossible_things, key=impossible_sort_key)

just_being_a_dict = {'foo ooo': [1, 2, 3], 'bar': [[4.0], [5.0], [6.0]],
                     'foo2': ['a', 'b', 'c'], 'foo3': ['a', 'b'], 3: 'bar', 33: 'barbar', 'rien': None}

counted_string = collections.Counter('abcdeabcdabcaba')

SomePoint = collections.namedtuple('Point', ['x', 'y'])
the_whole_point = SomePoint(x=42, y=42)

# Fluent python example  ======================

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


current_deck = FrenchDeck()
beer_card = Card('7', 'diamonds')


class DemoClass:
    special_taxi = 1729  # Regular class attribute

    def __init__(self):
        self.same_place = None

    # Example for dynamic vs static
    @property
    def ten(self):
        return 10

    def do_stuff(self):
        """
        A function for doing stuff

        Lots of documentation about all the stuff it does
        Probably some parameter descriptions too
        """

        # Assign to instance attribute
        self.same_place = ("""‘Now, here, you see, it takes all the running you can do, to keep in the same place. """,
                           """If you want to get somewhere else, you must run at least twice as fast as that!‘”'""")

        # Assign to class attribute
        DemoClass.jam_rules = collections.defaultdict(set,
                                                      {'DAY_PlUS_ONE': {'jam', 'tomorrow'},
                                                       'DAY_MINUS_ONE': {'jam', 'yesterday'},
                                                       'DAY0': {'no_jam', 'today'}})

        # Return dict includes a self-reference
        return {24: 'x', 11: 'k', 3: 'c', 4: 'd', 33: self.do_stuff}


demo_class_instance = DemoClass()

def main():
    infinite_grid_of_one_ohm_resistors = 356
    print('Finishing main')


if __name__ == '__main__':
    main()
