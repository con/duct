# con-duct

[![codecov](https://codecov.io/gh/con/duct/graph/badge.svg?token=JrPazw0Vn4)](https://codecov.io/gh/con/duct)
[![PyPI version](https://badge.fury.io/py/con-duct.svg)](https://badge.fury.io/py/con-duct)
[![RRID](https://img.shields.io/badge/RRID-SCR__025436-blue)](https://identifiers.org/RRID:SCR_025436)

A lightweight wrapper that monitors the execution of commands, collecting resource usage data and system information.

The `con-duct` CLI provides multiple subcommands for working with execution data:
- **`run`**: Execute and monitor commands (also available via the `duct` convenience alias)
- **`pp`**: Pretty-print JSON logs
- **`plot`**: Visualize resource usage
- **`ls`**: List execution information

Also see our [Datalad Blog Post](https://blog.datalad.org/posts/intro-duct-tion/) for a hands on example.

## Installation

Basic installation (includes `con-duct run` and `duct` commands):

    pip install con-duct

With optional helpers for visualization and analysis (`pp`, `plot`, `ls` commands):

    pip install con-duct[all]

## Quickstart

Try it out using either `duct` or `con-duct run`:

    duct --sample-interval 0.5 --report-interval 1 test/data/test_script.py --duration 3 --memory-size=1000

`duct` is most useful when the report-interval is less than the duration of the script.

## Summary

`con-duct` monitors command execution, collecting execution time, system information, and resource usage statistics of the command and all its child processes. It's intended to simplify recording resources necessary to execute a command, particularly in HPC environments.

## Command Reference

### con-duct

<!-- BEGIN EXTRAS HELP -->
<!-- END EXTRAS HELP -->

### con-duct run / duct

<!-- BEGIN HELP -->
<!-- END HELP -->

## FAQs

### git-annex add keeps adding duct logs directly into git

By default, [git-annex](https://git-annex.branchable.com/) treats all dotfiles, and files under directories starting with a `.` as "small" regardless of `annex.largefiles` setting [[ref: an issue describing the logic](https://git-annex.branchable.com/bugs/add__58___inconsistently_treats_files_in_dotdirs_as_dotfiles/?updated#comment-efc1f2aa8f46e88a8be9837a56cfa6f7)].
It is necessary to set `annex.dotfiles` variable to `true` to make git-annex treat them as regular files and thus subject to `annex.largefiles` setting [[ref: git-annex config](https://git-annex.branchable.com/git-annex-config/)].
Could be done the repository (not just specific clone, but any instance since records in `git-annex` branch) wide using `git annex config --set annex.dotfiles true`.
