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

environment variables:
  Many duct options can be configured by environment variables (which are
  overridden by command line options).

  DUCT_LOG_LEVEL: see --log-level
  DUCT_OUTPUT_PREFIX: see --output-prefix
  DUCT_SUMMARY_FORMAT: see --summary-format
  DUCT_SAMPLE_INTERVAL: see --sample-interval
  DUCT_REPORT_INTERVAL: see --report-interval
  DUCT_CAPTURE_OUTPUTS: see --capture-outputs
  DUCT_MESSAGE: see --message

positional arguments:
  command [command_args ...]
                        The command to execute, along with its arguments.
  command_args          Arguments for the command.

options:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
  -p OUTPUT_PREFIX, --output-prefix OUTPUT_PREFIX
                        File string format to be used as a prefix for the
                        files -- the captured stdout and stderr and the
                        resource usage logs. The understood variables are
                        {datetime}, {datetime_filesafe}, and {pid}. Leading
                        directories will be created if they do not exist. You
                        can also provide value via DUCT_OUTPUT_PREFIX env
                        variable. (default:
                        .duct/logs/{datetime_filesafe}-{pid}_)
  --summary-format SUMMARY_FORMAT
                        Output template to use when printing the summary
                        following execution. Accepts custom conversion flags:
                        !S: Converts filesizes to human readable units, green
                        if measured, red if None. !E: Colors exit code, green
                        if falsey, red if truthy, and red if None. !X: Colors
                        green if truthy, red if falsey. !N: Colors green if
                        not None, red if None (default: Summary: Exit Code:
                        {exit_code!E} Command: {command} Log files location:
                        {logs_prefix} Wall Clock Time: {wall_clock_time:.3f}
                        sec Memory Peak Usage (RSS): {peak_rss!S} Memory
                        Average Usage (RSS): {average_rss!S} Virtual Memory
                        Peak Usage (VSZ): {peak_vsz!S} Virtual Memory Average
                        Usage (VSZ): {average_vsz!S} Memory Peak Percentage:
                        {peak_pmem:.2f!N}% Memory Average Percentage:
                        {average_pmem:.2f!N}% CPU Peak Usage:
                        {peak_pcpu:.2f!N}% Average CPU Usage:
                        {average_pcpu:.2f!N}% )
  --colors              Use colors in duct output. (default: False)
  --clobber             Replace log files if they already exist. (default:
                        False)
  -l {NONE,CRITICAL,ERROR,WARNING,INFO,DEBUG}, --log-level {NONE,CRITICAL,ERROR,WARNING,INFO,DEBUG}
                        Level of log output to stderr, use NONE to entirely
                        disable. (default: INFO)
  -q, --quiet           [deprecated, use log level NONE] Disable duct logging
                        output (to stderr) (default: False)
  --sample-interval SAMPLE_INTERVAL, --s-i SAMPLE_INTERVAL
                        Interval in seconds between status checks of the
                        running process. Sample interval must be less than or
                        equal to report interval, and it achieves the best
                        results when sample is significantly less than the
                        runtime of the process. (default: 1.0)
  --report-interval REPORT_INTERVAL, --r-i REPORT_INTERVAL
                        Interval in seconds at which to report aggregated
                        data. (default: 60.0)
  --fail-time FAIL_TIME, --f-t FAIL_TIME
                        If command fails in less than this specified time
                        (seconds), duct would remove logs. Set to 0 if you
                        would like to keep logs for a failing command
                        regardless of its run time. Set to negative (e.g. -1)
                        if you would like to not keep logs for any failing
                        command. (default: 3.0)
  -c {all,none,stdout,stderr}, --capture-outputs {all,none,stdout,stderr}
                        Record stdout, stderr, all, or none to log files. You
                        can also provide value via DUCT_CAPTURE_OUTPUTS env
                        variable. (default: all)
  -o {all,none,stdout,stderr}, --outputs {all,none,stdout,stderr}
                        Print stdout, stderr, all, or none to stdout/stderr
                        respectively. (default: all)
  -t {all,system-summary,processes-samples}, --record-types {all,system-summary,processes-samples}
                        Record system-summary, processes-samples, or all
                        (default: all)
  -m MESSAGE, --message MESSAGE
                        Record a descriptive message about the purpose of this
                        execution. You can also provide value via DUCT_MESSAGE
                        env variable. (default: )
  --mode {new-session,current-session}
                        Session mode: 'new-session' creates a new session for
                        the command (default), 'current-session' tracks the
                        current session instead of starting a new one. Useful
                        for tracking slurm jobs or other commands that should
                        run in the current session. (default: new-session)

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

positional arguments:
  {pp,plot,ls}          Available subcommands
    pp                  Pretty print a JSON log.
    plot                Plot resource usage for an execution.
    ls                  Print execution information for all matching runs.

options:
  -h, --help            show this help message and exit
  -l {NONE,CRITICAL,ERROR,WARNING,INFO,DEBUG}, --log-level {NONE,CRITICAL,ERROR,WARNING,INFO,DEBUG}
                        Level of log output to stderr, use NONE to entirely
                        disable.
  --version             show program's version number and exit

```
<!-- END EXTRAS HELP -->

## FAQs

### git-annex add keeps adding duct logs directly into git

By default, [git-annex](https://git-annex.branchable.com/) treats all dotfiles, and files under directories starting with a `.` as "small" regardless of `annex.largefiles` setting [[ref: an issue describing the logic](https://git-annex.branchable.com/bugs/add__58___inconsistently_treats_files_in_dotdirs_as_dotfiles/?updated#comment-efc1f2aa8f46e88a8be9837a56cfa6f7)].
It is necessary to set `annex.dotfiles` variable to `true` to make git-annex treat them as regular files and thus subject to `annex.largefiles` setting [[ref: git-annex config](https://git-annex.branchable.com/git-annex-config/)].
Could be done the repository (not just specific clone, but any instance since records in `git-annex` branch) wide using `git annex config --set annex.dotfiles true`.
