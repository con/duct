# duct

[![codecov](https://codecov.io/gh/con/duct/graph/badge.svg?token=JrPazw0Vn4)](https://codecov.io/gh/con/duct)
[![PyPI version](https://badge.fury.io/py/con-duct.svg)](https://badge.fury.io/py/con-duct)
[![RRID](https://img.shields.io/badge/RRID-SCR__025436-blue)](https://identifiers.org/RRID:SCR_025436)

Also see our [Datalad Blog Post](https://blog.datalad.org/posts/intro-duct-tion/) for a hands on example.

## Installation

    pip install con-duct

## Quickstart

Try it out!

    duct --sample-interval 0.5 --report-interval 1 test/data/test_script.py --duration 3 --memory-size=1000

`duct` is most useful when the report-interval is less than the duration of the script.

## Summary:

A process wrapper script that monitors the execution of a command.

<!-- BEGIN HELP -->
```shell
>duct --help

usage: duct [-h] [--version] [-p OUTPUT_PREFIX]
            [--summary-format SUMMARY_FORMAT] [--colors] [--clobber]
            [-l {NONE,CRITICAL,ERROR,WARNING,INFO,DEBUG}] [-q]
            [--sample-interval SAMPLE_INTERVAL]
            [--report-interval REPORT_INTERVAL] [--fail-time FAIL_TIME]
            [-c {all,none,stdout,stderr}] [-o {all,none,stdout,stderr}]
            [-t {all,system-summary,processes-samples}] [-m MESSAGE]
            [--mode {new-session,current-session}]
            command [command_args ...] ...

duct is a lightweight wrapper that collects execution data for an arbitrary
command.  Execution data includes execution time, system information, and
resource usage statistics of the command and all its child processes. It is
intended to simplify the problem of recording the resources necessary to
execute a command, particularly in an HPC environment.

Resource usage is determined by polling (at a sample-interval).
During execution, duct produces a JSON lines (see https://jsonlines.org) file
with one data point recorded for each report (at a report-interval).

limitations:
  Duct uses session id to track the command process and its children, so it
  cannot handle the situation where a process creates a new session.
  If a command spawns child processes, duct will collect data on them, but
  duct exits as soon as the primary process exits.

configuration:
  When jsonargparse is installed, all options can be configured via:
  - YAML config files (default paths or DUCT_CONFIG_PATHS environment
variable)
  - Environment variables with DUCT_ prefix (e.g., DUCT_SAMPLE_INTERVAL)
  - Command line arguments (highest precedence)

default config file locations:
['/etc/duct/config.yaml', '${XDG_CONFIG_HOME:-~/.config}/duct/config.yaml',
'.duct/config.yaml'], Note: default values below are the ones overridden by
the contents of: .duct/config.yaml

positional arguments:
  ARG:   command [command_args ...]
                        The command to execute, along with its arguments.
                        (required)
  ARG:   command_args   Arguments for the command.

options:
  ARG:   -h, --help     Show this help message and exit.
  ARG:   --version      show program's version number and exit
  ARG:   -p OUTPUT_PREFIX, --output-prefix OUTPUT_PREFIX
  ENV:   DUCT_OUTPUT_PREFIX
                        File string format to be used as a prefix for the
                        files -- the captured stdout and stderr and the
                        resource usage logs. The understood variables are
                        {datetime}, {datetime_filesafe}, and {pid}. Leading
                        directories will be created if they do not exist.
                        (type: str, default:
                        .duct/logs/{datetime_filesafe}-{pid}_)
  ARG:   --summary-format SUMMARY_FORMAT
  ENV:   DUCT_SUMMARY_FORMAT
                        Output template to use when printing the summary
                        following execution. Accepts custom conversion flags:
                        !S: Converts filesizes to human readable units, green
                        if measured, red if None. !E: Colors exit code, green
                        if falsey, red if truthy, and red if None. !X: Colors
                        green if truthy, red if falsey. !N: Colors green if
                        not None, red if None (type: str, default: Summary:
                        Exit Code: {exit_code!E} Command: {command} Log files
                        location: {logs_prefix} Wall Clock Time:
                        {wall_clock_time:.3f} sec Memory Peak Usage (RSS):
                        {peak_rss!S} Memory Average Usage (RSS):
                        {average_rss!S} Virtual Memory Peak Usage (VSZ):
                        {peak_vsz!S} Virtual Memory Average Usage (VSZ):
                        {average_vsz!S} Memory Peak Percentage:
                        {peak_pmem:.2f!N}% Memory Average Percentage:
                        {average_pmem:.2f!N}% CPU Peak Usage:
                        {peak_pcpu:.2f!N}% Average CPU Usage:
                        {average_pcpu:.2f!N}% )
  ARG:   --colors
  ENV:   DUCT_COLORS
                        Use colors in duct output. (default: False)
  ARG:   --clobber
  ENV:   DUCT_CLOBBER
                        Replace log files if they already exist. (default:
                        False)
  ARG:   -l {NONE,CRITICAL,ERROR,WARNING,INFO,DEBUG}, --log-level {NONE,CRITICAL,ERROR,WARNING,INFO,DEBUG}
  ENV:   DUCT_LOG_LEVEL
                        Level of log output to stderr, use NONE to entirely
                        disable. (type: <method 'upper' of 'str' objects>,
                        default: INFO)
  ARG:   -q, --quiet
  ENV:   DUCT_QUIET
                        [deprecated, use log level NONE] Disable duct logging
                        output (to stderr) (default: False)
  ARG:   --sample-interval SAMPLE_INTERVAL, --s-i SAMPLE_INTERVAL
  ENV:   DUCT_SAMPLE_INTERVAL
                        Interval in seconds between status checks of the
                        running process. Sample interval must be less than or
                        equal to report interval, and it achieves the best
                        results when sample is significantly less than the
                        runtime of the process. (type: float, default: 1.0)
  ARG:   --report-interval REPORT_INTERVAL, --r-i REPORT_INTERVAL
  ENV:   DUCT_REPORT_INTERVAL
                        Interval in seconds at which to report aggregated
                        data. (type: float, default: 60.0)
  ARG:   --fail-time FAIL_TIME, --f-t FAIL_TIME
  ENV:   DUCT_FAIL_TIME
                        If command fails in less than this specified time
                        (seconds), duct would remove logs. Set to 0 if you
                        would like to keep logs for a failing command
                        regardless of its run time. Set to negative (e.g. -1)
                        if you would like to not keep logs for any failing
                        command. (type: float, default: 3.0)
  ARG:   -c {all,none,stdout,stderr}, --capture-outputs {all,none,stdout,stderr}
  ENV:   DUCT_CAPTURE_OUTPUTS
                        Record stdout, stderr, all, or none to log files.
                        (type: <bound method parse of <enum 'Outputs'>>,
                        default: all)
  ARG:   -o {all,none,stdout,stderr}, --outputs {all,none,stdout,stderr}
  ENV:   DUCT_OUTPUTS
                        Print stdout, stderr, all, or none to stdout/stderr
                        respectively. (type: <bound method parse of <enum
                        'Outputs'>>, default: all)
  ARG:   -t {all,system-summary,processes-samples}, --record-types {all,system-summary,processes-samples}
  ENV:   DUCT_RECORD_TYPES
                        Record system-summary, processes-samples, or all
                        (type: <bound method parse of <enum 'RecordTypes'>>,
                        default: all)
  ARG:   -m MESSAGE, --message MESSAGE
  ENV:   DUCT_MESSAGE
                        Record a descriptive message about the purpose of this
                        execution. (type: str, default: )
  ARG:   --mode {new-session,current-session}
  ENV:   DUCT_MODE
                        Session mode: 'new-session' creates a new session for
                        the command (default), 'current-session' tracks the
                        current session instead of starting a new one. Useful
                        for tracking slurm jobs or other commands that should
                        run in the current session. (type: <bound method parse
                        of <enum 'SessionMode'>>, default: new-session)

```
<!-- END HELP -->

# con-duct suite

In addition to `duct`, this project also includes a set of optional helpers under the `con-duct` command.
These helpers may use 3rd party python libraries.

## Installation

    pip install con-duct[all]

## Extras Helptext

<!-- BEGIN EXTRAS HELP -->
```shell
>con-duct --help

usage: con-duct <command> [options]

A suite of commands to manage or manipulate con-duct logs.

default config file locations:
['/etc/duct/config.yaml', '${XDG_CONFIG_HOME:-~/.config}/duct/config.yaml',
'.duct/config.yaml']

options:
  ARG:   -h, --help     Show this help message and exit.
  ARG:   -l {NONE,CRITICAL,ERROR,WARNING,INFO,DEBUG}, --log-level {NONE,CRITICAL,ERROR,WARNING,INFO,DEBUG}
  ENV:   DUCT_LOG_LEVEL
                        Level of log output to stderr, use NONE to entirely
                        disable. (type: <method 'upper' of 'str' objects>,
                        default: INFO)
  ARG:   --version      show program's version number and exit

subcommands:
For more details of each subcommand, add it as an argument followed by
--help.

  ARG:   {pp,plot,ls}   Available subcommands
    ARG:   pp           Pretty print a JSON log.
    ARG:   plot         Plot resource usage for an execution.
    ARG:   ls           Print execution information for all matching runs.

```
<!-- END EXTRAS HELP -->

## FAQs

### git-annex add keeps adding duct logs directly into git

By default, [git-annex](https://git-annex.branchable.com/) treats all dotfiles, and files under directories starting with a `.` as "small" regardless of `annex.largefiles` setting [[ref: an issue describing the logic](https://git-annex.branchable.com/bugs/add__58___inconsistently_treats_files_in_dotdirs_as_dotfiles/?updated#comment-efc1f2aa8f46e88a8be9837a56cfa6f7)].
It is necessary to set `annex.dotfiles` variable to `true` to make git-annex treat them as regular files and thus subject to `annex.largefiles` setting [[ref: git-annex config](https://git-annex.branchable.com/git-annex-config/)].
Could be done the repository (not just specific clone, but any instance since records in `git-annex` branch) wide using `git annex config --set annex.dotfiles true`.
