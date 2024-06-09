# duct

[![codecov](https://codecov.io/gh/con/duct/graph/badge.svg?token=JrPazw0Vn4)](https://codecov.io/gh/con/duct)

## Summary:

A process wrapper script that monitors the execution of a command.

```shell
> duct --help

<!--- BEGIN HELP -->
usage: duct [-h] [--version] [-p OUTPUT_PREFIX]
            [--sample-interval SAMPLE_INTERVAL]
            [--report-interval REPORT_INTERVAL] [-c {all,none,stdout,stderr}]
            [-o {all,none,stdout,stderr}]
            [-t {all,system-summary,processes-samples}]
            command ...

Gathers metrics on a command and all its child processes.

positional arguments:
  command               The command to execute.
  inner_args            Arguments for the command.

optional arguments:
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
  --sample-interval SAMPLE_INTERVAL, --s-i SAMPLE_INTERVAL
                        Interval in seconds between status checks of the
                        running process. Sample interval should be larger than
                        the runtime of the process or `duct` may underreport
                        the number of processes started. (default: 1.0)
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
<!--- END HELP -->
```

## Testing:

```shell
❯ ./test_script.py --help
test_script.py is a test script to consume CPU and memory.

options:
  -h, --help            show this help message and exit
  --duration DURATION   Duration to run the test in seconds.
  --cpu-load CPU_LOAD   Load factor to simulate CPU usage.
  --memory-size MEMORY_SIZE
                        Amount of memory to allocate in MB.

duct --report-interval 4 ./test_script.py --duration 12 --cpu-load 50000 --memory-size 50
```
