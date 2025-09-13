# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Test Commands
- Use `python -m venv .venv` to create a virtual environment
- Use `source .venv/bin/activate` to activate a virtual environment
- Install: `python -m pip install -e .[all]`
- Run all tests: `tox`
- Run specific test file: `tox -- -s -v test/test_file.py`
- Run specific test: `tox -e py3 -s -v -o addopts="" test/test_file.py::test_function`
- Lint: `tox -e lint`
- Type check: `tox -e typing`

## Development and Project Structure
- this project contains 2 entry points:
  - 'duct' is used for execution
    - duct should have no external dependencies
    - all duct code should live in @src/con_duct/__main__.py
  - 'con-duct' is used to work with duct logs
    - con-duct may have external dependencies 
    - con-duct argparse live in @src/con_duct/suite/main.py
    - each con-duct command has a separate file.


- All tests are under `tests/` folder
- `pytest` package is used for testing
- Project by default uses only standard Python libraries
  - if additional library is needed, should go under "all" of `options.extras_require` within `setup.cfg`
- @CONTRIBUTING.rst might provide more information about releasing etc

## Code Style Guidelines
- use pre-commit to fix style 
- Types: Use strict typing with annotations; `from __future__ import annotations`
- Naming: Classes (PascalCase), functions/variables (snake_case), constants (UPPER_SNAKE_CASE)
- Error handling: Use explicit try/except with informative messages; log exceptions
- Documentation: Use indented docstrings with complete parameter descriptions

When making changes, follow existing patterns in surrounding code.
