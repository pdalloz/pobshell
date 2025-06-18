myset = {10, 20, 30}

data = {'a': {'b': {'c': 'd'}}}
tricky_key_data = {'0': 'Zero the string',
                   0: 'Zero the number',
                   'has/a/slash': 42,
                   'a': {'b': 'We had b as a key elsewhere too'},
                   '1+2': 'looks like a calculation',
                   '2*3': 'another calculation look-a-ike',
                   (1, "2"): 'Ohh a tuuple',
                   ("1", 2, 3j): 'A second tuple or am I imagining it?',
                   (1.1, 2.2): "In fact we have several tuples",
                   (1.1, 2.2): (None, ("It's tuples all the way down", (123, 99))),
                   (1.1, (2.2, 3.3)): "Don't we all love nested tuples?",
                   "(1.1, 2.2)": "Not in fact a tuple, it's a string",

                   }
target = {
    'system': {
        'planets': [
            {
                'name': 'earth',
                'moons': [
                    {'name': 'luna'}
                ]
            },
            {
                'name': 'jupiter',
                'moons': [
                    {'name': 'io'},
                    {'name': 'europa'}
                ]
            }
        ]
    }
}

cafe_menu = ['egg and bacon', 'egg sausage and bacon', 'egg and spam', 'egg bacon and spam',
             'egg bacon sausage and spam',
             'spam bacon sausage and spam', 'spam egg spam spam bacon and spam',
             'spam sausage spam spam bacon spam tomato and spam']

nested_list = ["a", "b", "c", ["001", "010", "011", [1, 2, "christmas"]]]

import pobshell

pobshell.shell()
# pob.shell(root=cafe_menu)
