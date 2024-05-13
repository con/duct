# duct

[![codecov](https://codecov.io/gh/con/duct/graph/badge.svg?token=JrPazw0Vn4)](https://codecov.io/gh/con/duct)

## Summary:

A process wrapper script that monitors the execution of a command.

```shell
> duct --help

usage: duct [-h] [--sample-interval SAMPLE_INTERVAL]
            [--output_prefix OUTPUT_PREFIX]
            [--report-interval REPORT_INTERVAL]
            command [arguments ...]

Duct creates a new session to run a command and all its child processes, and
the collects metrics for all processes in the session.

positional arguments:
  command               The command to execute.
  arguments             Arguments for the command.

options:
  -h, --help            show this help message and exit
  --sample-interval SAMPLE_INTERVAL
                        Interval in seconds between status checks of the
                        running process.
  --output_prefix OUTPUT_PREFIX
                        Directory in which all logs will be saved.
  --report-interval REPORT_INTERVAL
                        Interval in seconds at which to report aggregated
                        data.
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

duct --report-interval 4 -- ./test_script.py --duration 12 --cpu-load 50000 --memory-size 50 | jq
```
