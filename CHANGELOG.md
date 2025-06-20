# Changelog

All notable changes to this project will be documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com).

## [0.1.1] - 2025-06-20
### Changed
- `Pobshell` now defaults to `Pobprefs.DEBUG = False` instead of `DEBUG = True`
- `DEBUG` is now an optional keyword argument to pobshell.shell() and .pob()

### Internal
- Test file paths updated to use more generic environment names

## [0.1.0] - 2025-06-19
### Added
- Initial release of Pobshell
- Core commands: ls, cat, doc, tree, find, memsize, etc.
- Bash-style navigation for Python objects
- Filter system (`--isfunction`, `--doc PATTERN`, etc.)
- OS shell integration with pipes and `!` commands
- `map` modes: attributes, contents, everything, static,...
- Alpha-level safety precautions

