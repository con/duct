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
            [--summary-format SUMMARY_FORMAT] [--clobber] [-q]
            [--sample-interval SAMPLE_INTERVAL]
            [--report-interval REPORT_INTERVAL] [-c {all,none,stdout,stderr}]
            [-o {all,none,stdout,stderr}]
            [-t {all,system-summary,processes-samples}]
            command [command_args ...] ...

Gathers metrics on a command and all its child processes.

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
                        following execution. (default: Exit Code: {exit_code}
                        Command: {command} Log files location: {logs_prefix}
                        Wall Clock Time: {wall_clock_time} sec Memory Peak
                        Usage (RSS): {peak_rss} Memory Average Usage (RSS):
                        {average_rss} Virtual Memory Peak Usage (VSZ):
                        {peak_vsz} Virtual Memory Average Usage (VSZ):
                        {average_vsz} Memory Peak Percentage: {peak_pmem}
                        Memory Average Percentage: {average_pmem} CPU Peak
                        Usage: {peak_pcpu} Average CPU Usage: {average_pcpu}
                        Samples Collected: {num_samples} Reports Written:
                        {num_reports} )
  --clobber             Replace log files if they already exist. (default:
                        False)
  -q, --quiet           Suppress duct output. (default: False)
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
