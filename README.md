# con/duct-or - helper to execute and monitor a process

The origin: in ReproMan (reproman run) we do already collect stdout/stderr but otherwise do not collect any statistics about execution of a command.
In DataLad (datalad run) we do not collect anything, and just passthrough the stdout/stderr.
But capturing/storing such logs are most often desired.
Moreover knowing maximum memory utilization could be critical for adequate resource requests for batch jobs.

## ChatGPT prototype

For the request/question:

is there a helper for linux to run a command while that helper would also capture and store somewhere std output and stderr, while also monitoring underlying process(es) for their memory consumption, start/stop endtimes, etc and then provide  a json-formatted record with that upon completion (also with the exit code of the command).

it gave:

```bash
#!/bin/bash

# Command to execute
COMMAND="$*"

# Redirect stdout and stderr to files
STDOUT_FILE=$(mktemp)
STDERR_FILE=$(mktemp)

# Record start time
START_TIME=$(date +%s)

# Execute command
eval "$COMMAND" 1>$STDOUT_FILE 2>$STDERR_FILE &
PID=$!

# Wait for the command to finish
wait $PID
EXIT_CODE=$?

# Record end time
END_TIME=$(date +%s)

# Get memory usage (max resident set size)
MEMORY_USAGE=$(cat /proc/$PID/status | grep VmHWM | awk '{print $2}')

# Generate JSON output
jq -n \
    --arg cmd "$COMMAND" \
    --arg stdout "$(cat $STDOUT_FILE)" \
    --arg stderr "$(cat $STDERR_FILE)" \
    --argjson exit_code "$EXIT_CODE" \
    --argjson start_time "$START_TIME" \
    --argjson end_time "$END_TIME" \
    --argjson memory_usage "$MEMORY_USAGE" \
    '{command: $cmd, stdout: $stdout, stderr: $stderr, exit_code: $exit_code, start_time: $start_time, end_time: $end_time, memory_usage_kb: $memory_usage}'

# Clean up
rm $STDOUT_FILE $STDERR_FILE
```

## Desired features/usecases

- be configurable. Most likely 
- output filenames 

## Initial implementation details

- Since destined ATM for tools which are in datalad space can just use DataLad's Runner construct, smth like

    out = Runner().run([cmd[0], '-c', 'datalad.dummy=this'] + cmd[1:], protocol=StdOutErrCapture)

but we might want custom/derived protocol so we can capture and also at once output...

- For monitoring -- we need stats on the entire "child tree" and it could be under singularity... I guess we would not be able to monitor server'ish docker 

  - may be via cgroups somehow?
  - may be there is already a tool? how brainlife does it?

- Would be nice to collect it through time evolution to plots the graphs but then in the .json itself have only summaries over those monitored parameters

  - again -- look into brainlife?
