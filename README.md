# duct

[![codecov](https://codecov.io/gh/con/duct/graph/badge.svg?token=JrPazw0Vn4)](https://codecov.io/gh/con/duct)
[![PyPI version](https://badge.fury.io/py/con-duct.svg)](https://badge.fury.io/py/con-duct)

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
            [--report-interval REPORT_INTERVAL] [-c {all,none,stdout,stderr}]
            [-o {all,none,stdout,stderr}]
            [-t {all,system-summary,processes-samples}]
            command [command_args ...] ...

duct is a lightweight wrapper that collects execution data for an arbitrary
command.  Execution data includes execution time, system information, and
resource usage statistics of the command and all its child processes. It is
intended to simplify the problem of recording the resources necessary to
execute a command, particularly in an HPC environment.

Resource usage is determined by polling (at a sample-interval).
During execution, duct produces a JSON lines (see https://jsonlines.org) file
with one data point recorded for each report (at a report-interval).

environment variables:
  Many duct options can be configured by environment variables (which are
  overridden by command line options).

  DUCT_LOG_LEVEL: see --log-level
  DUCT_OUTPUT_PREFIX: see --output-prefix
  DUCT_SUMMARY_FORMAT: see --summary-format
  DUCT_SAMPLE_INTERVAL: see --sample-interval
  DUCT_REPORT_INTERVAL: see --report-interval
  DUCT_CAPTURE_OUTPUTS: see --capture-outputs

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
                        {peak_pmem!N}% Memory Average Percentage:
                        {average_pmem!N}% CPU Peak Usage: {peak_pcpu!N}%
                        Average CPU Usage: {average_pcpu!N}% )
  --colors              Use colors in duct output. (default: False)
  --clobber             Replace log files if they already exist. (default:
                        False)
  -l {NONE,CRITICAL,ERROR,WARNING,INFO,DEBUG}, --log_level {NONE,CRITICAL,ERROR,WARNING,INFO,DEBUG}
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

A command-line tool for managing various tasks.

positional arguments:
  {pp}        Available subcommands
    pp        Pretty print a JSON log

options:
  -h, --help  show this help message and exit

```
<!-- END EXTRAS HELP -->
