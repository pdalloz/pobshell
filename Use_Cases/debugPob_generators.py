# All generator definitions

def simple_generator():
    for i in range(3):
        yield i

def generator_with_state():
    x = 10
    yield x
    x += 5
    yield x

def generator_with_send():
    val = yield "Start"
    while True:
        val = yield f"Received: {val}"

def generator_with_finally():
    try:
        yield 1
        yield 2
    finally:
        print("Cleanup done")

def subgen():
    yield 'a'
    yield 'b'

def nested_generator():
    yield 1
    yield from subgen()
    yield 2

def generator_with_exception_handling():
    try:
        yield "Ready"
        raise ValueError("Oops")
    except ValueError as e:
        yield f"Caught: {e}"
    yield "Done"

def generator_with_side_effects():
    print("Step 1")
    yield 1
    print("Step 2")
    yield 2

# Instantiate and advance each generator to leave them in interesting paused states

gens = {}

# 1. simple_generator paused after first yield
gens['simple'] = simple_generator()
next(gens['simple'])

# 2. generator_with_state paused after first yield
gens['state'] = generator_with_state()
next(gens['state'])

# 3. generator_with_send paused after yielding "Start"
gens['send'] = generator_with_send()
next(gens['send'])  # send() won't work until first yield is done

# 4. generator_with_finally paused after first yield
gens['finally'] = generator_with_finally()
next(gens['finally'])

# 5. nested_generator paused inside subgen
gens['nested'] = nested_generator()
next(gens['nested'])  # 1
next(gens['nested'])  # 'a'

# 6. generator_with_exception_handling paused at yield before exception
gens['exception'] = generator_with_exception_handling()
next(gens['exception'])

# 7. generator_with_side_effects paused after printing Step 1
gens['side_effect'] = generator_with_side_effects()
next(gens['side_effect'])

# At this point, all generators are partially advanced and can be inspected.
# For example, Pobshell can be used here to inspect `gens` or individual generators.

import pobshell
pobshell.shell()

