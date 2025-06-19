# Pobshell

*A Bash‑like shell for live Python objects.*

Think `cd`, `ls`, `cat`, and `find` — but for **Python objects** instead of files. Stroll around your code, runtime state, and data structures. Inspect everything: modules, classes, live objects. It's pick‑up‑and‑play: familiar commands plus optional new tricks. A fun and genuinely useful way to explore a Python app, package, or Python itself.

---

## What Is Pobshell For?

- **Exploratory debugging** – Inspect live object state on the fly
- **Understanding APIs** – Examine code, docstrings, class trees
- **Shell integration** – Pipe object state or code snippets to LLMs or OS tools
- **Code and data search** – Recursive search for object state or source without file paths
- **REPL & paused scripts** – Explore runtime environments dynamically
- **Teaching & demos** – Make Python internals visible and walkable

---

## How It Works

Pobshell maps Python objects to Linux‑style paths:

- Each object is a "directory"
- Each attribute or member is a child in that directory
- Navigate using **Bash-style commands**

For example:

```
/ ▶ cd json
/json ▶ ls
/json ▶ cd JSONDecodeError
/json/JSONDecodeError ▶ ls -l
```

---

## Command targets

- **Omit target** — operates on *all* members of the current object. Use `-a` to include private attributes & dunders.  
  *E.g.* `/json/JSONDecodeError ▶ ls -la`
- **`*pattern*`** — operates on members with matching names.  
  *E.g.* `/json ▶ ls -l *Decode*`
- **`/path` (no trailing slash)** — treat that object itself as the target.  
  *E.g.* `/ ▶ ls -l /json/JSONDecodeError`
- **`/path/` (trailing slash)** — operate on *members* of that object.  
  *E.g.* `/ ▶ ls -l /json/JSONDecodeError/`

---

## Core Commands

Pobshell commands are built on Python’s `inspect` module (mostly).

| Command  | Description                                   |
|----------|-----------------------------------------------|
| `ls`     | List object members                           |
| `ls -l`  | Long listing: names, types, values            |
| `cat`    | Show syntax‑highlighted source code           |
| `doc`    | Print docstrings                              |
| `abcs`   | Show abstract base classes                    |
| `predicates` | Inspect predicates (e.g. `isclass`)       |
| `memsize` | Total memory size of object and members      |
| `tree`   | Diagram object structure                      |
| `find`   | Recursive search                              |

Other commands: `mro`, `pydoc`, `repr`, `type`, `signature`, `filepath`, ...

---

## Filters

Most commands work on the *members* of the current object. Use filters to control what is inspected. Filter members by type, docstring, source, str representation, Python expression, …

- `--isfunction`, `--ismodule`, `--isclass`, etc.  
  *E.g.* `/path ▶ doc -1 --ismodule`
- `--doc PATTERN` or `--cat PATTERN`  
  *E.g.* `/path ▶ cat -n 4 --doc *Encoding*`  
  *E.g.* `/path ▶ doc --cat "class\\s+oyster" -ir`  
  *E.g.* `/path ▶ find . --cat *TODO* -i`
- `--str PATTERN`, `--mro PATTERN`, `--abcs PATTERN`  
  *E.g.* `/iris/data ▶ ls -l --str *6.3*`
- `--matchpy PYTHON_EXPR`  
  *E.g.* `/path ▶ find --matchpy "isinstance(self, Cafe)"`

---

## OS Shell Integration

- **Pipes and redirection**  
  *E.g.* `/path ▶ ls -lu | sort -k 2`
- **Run OS commands with `!`** — prefix a shell command with `!`; wrap any Pobshell command in `"""..."""` to execute it first and substitute its output via a temporary file.
  *E.g.* `/json ▶ !diff  """cat dump"""  """cat dumps"""`  
  *E.g.* `/path ▶ !aichat -f """cat ns_path_complete""" Explain how this code works`

---

## Exploring Data Structures

Pobshell lets you *remap* what you see when you `cd` into an object. Use the `map` command to switch modes:

- **attributes** — show only the object’s attributes (default)
- **contents** — show only collection items (`list`, `dict`, …)
- **everything** — show attributes **and** collection items together
- **static** — read raw `__dict__` values, so no descriptor or `__getattr__` code is executed

When working with contents, use backticks around any "name" not valid as a Python identifier:

```
/path ▶ ls /mylist/`0`                    # list index
/path ▶ cd /mydict/`'0'`                  # string key
/path ▶ predicates /sympy/.../`exp`       # symbolic key
/path ▶ ls -x "/mydict/`foo bar`"         # space in key
```

Python expressions inside filters and commands:

```
/path ▶ ls -x --matchpy "isinstance(self, Cafe)"
/path ▶ find --typename list --printpy "self[-1]"
/path ▶ printpy "sum(self)" /iris/data
/path ▶ ::import inspect    # add inspect module as a member of root
/path ▶ ::x = 42            # assign x in root
```

---

## Features

- Tab completion & history
- Syntax coloring and pagination
- Shortcuts, macros, aliases
- Supports light and dark themes

---

## Safety & Stability

- Pobshell is in alpha release
- Read‑only by default. Commands such as `ls`, `doc`, and `cat` simply inspect live objects — like pausing in a debugger.
- When can things change? Only if you run Python code (`printpy`, `matchpy`, `:` or `::`) or if a property fires.
- Need zero‑side‑effects? Switch to **`map static`** to fetch raw `__dict__` values without executing descriptors or `__getattr__` logic.
- Sandboxing. Adding or removing names under the root path `/` is local to Pobshell. Edits you make to existing mutable objects (lists, dicts, class attrs) will reflect in your program, just like in a REPL.

---

## Installation

Pobshell supports Python 3.12. It has minimal dependencies.

```shell
$ pip install pobshell
```

---

## Platform Compatibility (tested)

| Platform         | Python | Basic func. | Tab completion | Unit tests |
|------------------|--------|--------------|----------------|-------------|
| macOS            | 3.12   | Yes          | Yes            | Yes         |
| Linux            | 3.12   | Yes          | Yes            | ?           |
| Win 10 WSL       | 3.13   | Yes          | Yes            | Yes         |
| Win 10 Native    | 3.12   | Yes          | Yes            | Yes         |
| Win 10 Native    | 3.13   | Yes          | No             | No          |

---

## Quickstart

```python
>>> import pobshell; pobshell.shell()
/ ▶ ls -l
```

`shell()` creates a Pobshell virtual filesystem, populates root with globals and locals of the calling frame, and starts a Pobshell command loop. You get a prompt at root for entering Pobshell commands. Use `quit` to exit.

---

## Contribute

GitHub: https://github.com/pdalloz/pobshell  
Bug reports, feature ideas, and pull requests welcome!

---

## About the Author

Developed and maintained by **Peter Dalloz**, data lead and Python engineer.

If you're looking for help with a data or AI project, or any Python codebase, feel free to reach out via LinkedIn. I'm open to permanent onsite roles in the UK (citizen) or Spain (resident), and remote or contract work globally.
LinkedIn: https://www.linkedin.com/in/pdalloz


