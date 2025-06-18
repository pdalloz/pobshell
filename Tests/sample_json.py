# Tests are take from jmespath test suite & examples (not a complete set)
# https://pypi.org/project/jmespath/
# https://jmespath.org/examples.html

import pobshell
# PApp = pobshell.Pobiverse()
# run_cmd(PApp, 'set contents true')
# run_cmd(PApp, 'cd /')
# out = run_cmd(PApp, "find /dynamic_test_code/FrenchDeck/ -name `3` -depthfirst -winner 'pobns.depth'", norm=True)




a = {'foo': {'bar': {'baz': 'correct'}}}
#  test: foo.bar.baz  -> 'correct'

b = {'foo': ['zero', 'one', 'two']}
# foo[1] -> 'one'
# foo[*] -> ['zero', 'one', 'two']

c = {'foo': [{'bar': 'one'}, {'bar': 'two'}]}
# foo[*].bar -> ['one', 'two']

d = {'foo': 'foo'}
# foo || bar -> 'foo'
f = {'bar': 'bar'}
# foo || bar -> 'bar'
g = {'foo': 'foo', 'bar': 'bar'}
# foo || bar -> 'foo'
d = {'goo': 'goo'}
# foo || bar -> None


e = {'foo': {'foo': 'foo'}}
# foo.foo || foo.bar -> 'foo'
h = {'foo': {'bar': 'bar'}}
# foo.foo || foo.bar -> 'bar'
# foo.foo || foo.baz -> None
g = {'foo': 'foo', 'bar': 'bar'}


i = {'foo': {'bar': 'bar', 'baz': 'baz', 'qux': 'qux'}}
j = {'foo': {'bar': {'baz': 'CORRECT'}, 'qux': 'qux'}}
k = {
    'foo': [
        {'bar': [{'baz': 'one'}, {'baz': 'two'}]},
        {'bar': [{'baz': 'three'}, {'baz': 'four'}, {'baz': 'five'}]},
    ]
}


l = {'top1': {'foo': 'bar'}, 'top2': {'foo': 'baz'},
     'top3': {'notfoo': 'notfoo'}}

m = {'foo': 'a', 'bar': 'b', 'baz': 'c'}

n = {'foo\tbar': 'baz'}
o = {'foo\nbar': 'baz'}
p = {'foo\bbar': 'baz'}
q = {'foo\fbar': 'baz'}
r = {'foo\rbar': 'baz'}

s = {'foo\\nbar': 'baz'}
t = {'foo\n\t\rbar': 'baz'}

u = {
            'foo': {
                'one': {
                    'a': {'c': 'CORRECT', 'd': 'other'},
                    'b': {'c': 'ALSOCORRECT', 'd': 'other'},
                },
                'two': {
                    'a': {'c': 'CORRECT', 'd': 'other'},
                    'c': {'c': 'WRONG', 'd': 'other'},
                },
            }
        }

v = {
            "foo": [
                [["one", "two"], ["three", "four"]],
                [["five", "six"], ["seven", "eight"]],
                [["nine"], ["ten"]]
            ]
        }

# Examples below are from:
# https://jmespath.org/examples.html
w = {
  "people": [
    {
      "age": 20,
      "other": "foo",
      "name": "Bob"
    },
    {
      "age": 25,
      "other": "bar",
      "name": "Fred"
    },
    {
      "age": 30,
      "other": "baz",
      "name": "George"
    }
  ]
}
# taking an array of hashes, and simplifying down to an array of two element arrays containing a name and an age.
# We’re also only including list elements where the age key is greater than 20

# people[?age > `20`].[name, age]
# ->
# [
#   [
#     "Fred",
#     25
#   ],
#   [
#     "George",
#     30
#   ]
# ]

# If instead we want to create the same hash structure but only include the age and name key, we can instead say
# people[?age > `20`].{name: name, age: age}
# ->
# [
#   {
#     "name": "Fred",
#     "age": 25
#   },
#   {
#     "name": "George",
#     "age": 30
#   }
# ]

# people[*].{name: name, tags: tags[0]}
# Notice in this example instead of applying a filter expression ([? <expr> ]),
# we’re selecting all array elements via [*].
# ->
# [
#   {
#     "name": "Bob",
#     "tags": "a"
#   },
#   {
#     "name": "Fred",
#     "tags": "d"
#   },
#   {
#     "name": "George",
#     "tags": "g"
#   }
# ]

# nested data ================
x = {
  "reservations": [
    {
      "instances": [
        {"type": "small",
         "state": {"name": "running"},
         "tags": [{"Key": "Name",
                   "Values": ["Web"]},
                  {"Key": "version",
                   "Values": ["1"]}]},
        {"type": "large",
         "state": {"name": "stopped"},
         "tags": [{"Key": "Name",
                   "Values": ["Web"]},
                  {"Key": "version",
                   "Values": ["1"]}]}
      ]
    }, {
      "instances": [
        {"type": "medium",
         "state": {"name": "terminated"},
         "tags": [{"Key": "Name",
                   "Values": ["Web"]},
                  {"Key": "version",
                   "Values": ["1"]}]},
        {"type": "xlarge",
         "state": {"name": "running"},
         "tags": [{"Key": "Name",
                   "Values": ["DB"]},
                  {"Key": "version",
                   "Values": ["1"]}]}
      ]
    }
  ]
}

# reservations[].instances[].[tags[?Key=='Name'].Values[] | [0], type, state.name]
#               NB [] -> Flattening operator
#                       The flattening operator will merge sublists in the current result into a single list.
# ->
# [
#   [
#     "Web",
#     "small",
#     "running"
#   ],
#   [
#     "Web",
#     "large",
#     "stopped"
#   ],
#   [
#     "Web",
#     "medium",
#     "terminated"
#   ],
#   [
#     "DB",
#     "xlarge",
#     "running"
#   ]
# ]

# Filtering and Selecting Nested Data ---------------------
y = {
  "people": [
    {
      "general": {
        "id": 100,
        "age": 20,
        "other": "foo",
        "name": "Bob"
      },
      "history": {
        "first_login": "2014-01-01",
        "last_login": "2014-01-02"
      }
    },
    {
      "general": {
        "id": 101,
        "age": 30,
        "other": "bar",
        "name": "Bill"
      },
      "history": {
        "first_login": "2014-05-01",
        "last_login": "2014-05-02"
      }
    }
  ]
}

# people[?general.id==`100`].general | [0]
# ->
# {
#   "id": 100,
#   "age": 20,
#   "other": "foo",
#   "name": "Bob"
# }

z = {
  "locations": [
    {"name": "Seattle", "state": "WA"},
    {"name": "New York", "state": "NY"},
    {"name": "Bellevue", "state": "WA"},
    {"name": "Olympia", "state": "WA"}
  ]
}
# locations[?state == 'WA'].name | sort(@)[-2:] | {WashingtonCities: join(', ', @)}
# ->
# {
#   "WashingtonCities": "Olympia, Seattle"
# }
# We can think of this JMESPath expression as having three components, each
# separated by the pipe character |. The first expression is familiar to us,
# it’s similar to the first example on this page. The second part of the
# expression, sort(@), is similar to the sort_by function we saw in the previous
# section. The @ token is used to refer to the current element. The sort
# function takes a single parameter which is an array. If the input JSON
# document was a hash, and we wanted to sort the foo key, which was an array, we
# could just use sort(foo). In this scenario, the input JSON document is the
# array we want to sort. To refer to this value, we use the current element, @,
# to indicate this. We’re also only taking a subset of the sorted array. We’re
# using a slice ([-2:]) to indicate that we only want the last two elements in
# the sorted array to be passed through to the final third of this expression.

pobshell.shell(persistent_history_file=None)
