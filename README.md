# duct

## Summary:

duct - run a not-so-simple command and collect resource usage metrics

`duct [options] command [arguments...]`

Duct creates a new session to run a command and all its child processes, and the collects metrics for all processes in the session.

## Options:
   - `--sample-interval`: SECONDS, how frequently to poll the processes
   - `--report-interval`: SECONDS, how frequently data is recorded. All samples within this interval will be aggregated when reported.


## TODO:
   - `--output-prefix`:  (`DUCT_OUTPUT_PREFIX` env var), defaulting to what we have in https://github.com/con/duct/blob/main/duct_time#L3C25-L3C40 - time based etc. Make it an f-string.
   - `--number_of_sample_aggregated` : INT
   - `--capture-outputs all,none,stdout,stderr` . For starters -- when we set it to capture, we do not show those to terminal. Making it `none` is simplest, but then you would not capture any stdout/stderr and files should not be generated. just point to the output files whenever it is captured, not `subprocess.PIPE`.
   - `--outputs none,outputs,spinner,dotter`. none -- capturing would produce no output, `"outputs"` -- we would have a thread monitoring those output files and reading from them and dumping to `stdout` `stderr` . Later might be done smarter way through direct Popen orchestration of execution similarly to how we do in datalad. `spinner` -- use some fancy to your liking spinning wheel in terminal (e.g. sequence of `/-\-` with `\r` to go back and stats on the process so far (time, max mem etc)) upon receiving some block of outputs. Dotter - similar to before but then use `.` instead of some fancy spinner with -r.
   - `--record-types all,system-summary,processes-samples,processes-summary`  (`DUCT_RECORD_TYPES`) -- ','-separated list of which record type(s) to bother collecting. By default -- `all`

## Testing:

`duct --report-interval 4 ./test_script.py -- --duration 12 --cpu-load 50000 --memory-size 50 | jq`
