# Telemetry Comparison: Kedro vs con-duct

This document demonstrates the telemetry and provenance tracking capabilities of Kedro compared to con-duct, as well as how they can work together with DataLad.

## Overview

Both Kedro and con-duct collect execution metadata, but with different focuses:

- **Kedro Telemetry**: Collects anonymous usage data to improve the product, including project statistics, pipeline information, and dataset types. It sends data to Heap Analytics (when network is available).
- **con-duct**: Collects detailed resource usage metrics (CPU, memory, runtime) and execution provenance. All data stays local in JSON files.

## Test Setup

We created a minimal Kedro project with:
- A simple pipeline that greets a name from parameters
- Output written to `output.txt`
- DataLad for version control

## Test Results

### Test 1: Kedro with Telemetry ENABLED (baseline)

```bash
$ kedro run
```

**Kedro Output:**
```
[02/10/26 15:31:50] INFO     Using logging configuration.
[02/10/26 15:31:50] INFO     Kedro project kedro_test
                    INFO     Kedro is sending anonymous usage data with the sole purpose 
                             of improving the product. No personal data or IP addresses 
                             are stored on our side. To opt out, set the 
                             `KEDRO_DISABLE_TELEMETRY` or `DO_NOT_TRACK` environment 
                             variables, or create a `.telemetry` file in the current 
                             working directory with the contents `consent: false`. 
                             To hide this message, explicitly grant or deny consent.
                             Read more at https://docs.kedro.org/en/stable/about/telemetry/
                    DEBUG    Failed to send data to Heap. Exception of type 
                             'ConnectionError' was raised.
                    INFO     Using synchronous mode for loading and saving data.
                    INFO     Loading data from params:name (MemoryDataset)...
                    INFO     Running node: greet() ->
                    INFO     Saving data to greeting (MemoryDataset)...
                    INFO     Completed node: greet__93018e38
                    INFO     Completed 1 out of 1 tasks
                    INFO     Pipeline execution completed successfully in 0.0 sec.
```

**What Kedro Telemetry Collects:**
- Project name and statistics (number of nodes, pipelines)
- Dataset types used in the project
- Kedro version and Python version
- Operating system information
- Pipeline execution events (start, completion)
- Sends to Heap Analytics (failed in our test due to network restrictions)

**Data Location:** Sent to external service (Heap Analytics)

---

### Test 2: Kedro with DataLad Run (telemetry enabled)

```bash
$ datalad run --output output.txt kedro run
```

**Output:**
```
[INFO] == Command start (output follows) =====
[02/10/26 15:31:51] INFO     Kedro is sending anonymous usage data...
                    DEBUG    Failed to send data to Heap. Exception of type 
                             'ConnectionError' was raised.
                    INFO     Pipeline execution completed successfully in 0.0 sec.
[INFO] == Command exit (modification check follows) =====
run(ok): /tmp/telemetry-comparison/kedro-test (dataset) [kedro run]
add(ok): output.txt (file)
save(ok): . (dataset)
```

**What DataLad Adds:**
- Command provenance in Git history
- Tracks input/output files
- Records exact command executed
- Git commit with message: `[DATALAD RUNCMD] Execute Kedro demo pipeline with DataLad`

**Data Location:** Git commit metadata in `.git/` directory

---

### Test 3: Kedro with con-duct (telemetry enabled)

```bash
$ duct --output-prefix /tmp/duct-kedro- kedro run
```

**Output:**
```
2026-02-10T15:31:52+0000 [INFO] con-duct: No .env files found
2026-02-10T15:31:52+0000 [INFO] con-duct: duct 0.19.0.post61+gef60a0e is executing 'kedro run'...
2026-02-10T15:31:52+0000 [INFO] con-duct: Log files will be written to /tmp/duct-kedro-
[02/10/26 15:31:52] INFO     Kedro is sending anonymous usage data...
                    DEBUG    Failed to send data to Heap.
                    INFO     Pipeline execution completed successfully in 0.0 sec.
2026-02-10T15:31:52+0000 [INFO] con-duct: Summary:
Exit Code: 0
Command: kedro run
Log files location: /tmp/duct-kedro-
Wall Clock Time: 0.579 sec
Memory Peak Usage (RSS): 9.7 MB
Memory Average Usage (RSS): 9.7 MB
Virtual Memory Peak Usage (VSZ): 18.8 MB
Virtual Memory Average Usage (VSZ): 18.8 MB
Memory Peak Percentage: 0.00%
Memory Average Percentage: 0.00%
CPU Peak Usage: 0.00%
Average CPU Usage: 0.00%
```

**con-duct Files Created:**
```
-rw-rw-r-- 1 runner runner  976 Feb 10 15:31 /tmp/duct-kedro-info.json
-rw-rw-r-- 1 runner runner    0 Feb 10 15:31 /tmp/duct-kedro-stderr
-rw-rw-r-- 1 runner runner 2.5K Feb 10 15:31 /tmp/duct-kedro-stdout
-rw-rw-r-- 1 runner runner  461 Feb 10 15:31 /tmp/duct-kedro-usage.jsonl
```

**What con-duct Collects:**

*From `duct-kedro-info.json`:*
```json
{
    "command": "kedro run",
    "system": {
        "cpu_total": 4,
        "memory_total": 16771862528,
        "hostname": "runnervmwffz4",
        "uid": 1001,
        "user": "runner"
    },
    "duct_version": "0.19.0.post61+gef60a0e",
    "execution_summary": {
        "exit_code": 0,
        "wall_clock_time": 0.5795,
        "peak_rss": 9682944,
        "average_rss": 9682944,
        "peak_vsz": 18640896,
        "average_vsz": 18640896,
        "peak_pmem": 0.0,
        "average_pmem": 0.0,
        "peak_pcpu": 0.0,
        "average_pcpu": 0.0,
        "num_samples": 1,
        "start_time": 1770737513.375214,
        "end_time": 1770737513.954739,
        "working_directory": "/tmp/telemetry-comparison/kedro-test"
    }
}
```

*From `duct-kedro-usage.jsonl`:*
```json
{
    "timestamp": "2026-02-10T15:31:53.390237+00:00",
    "num_samples": 1,
    "processes": {
        "4864": {
            "pcpu": 0.0,
            "pmem": 0.0,
            "rss": 9682944,
            "vsz": 18640896,
            "timestamp": "2026-02-10T15:31:53.390237+00:00",
            "etime": "00:00",
            "stat": {"Rs": 1},
            "cmd": "/usr/bin/python3 /home/runner/.local/bin/kedro run"
        }
    },
    "totals": {
        "pmem": 0.0,
        "pcpu": 0.0,
        "rss": 9682944,
        "vsz": 18640896
    }
}
```

**Data Location:** Local JSON files at specified prefix

---

### Test 4: Combined - DataLad + con-duct + Kedro (all telemetry enabled)

```bash
$ datalad run --output output.txt duct --output-prefix /tmp/duct-kedro2- kedro run
```

**Output:**
```
[INFO] == Command start (output follows) =====
2026-02-10T15:31:53+0000 [INFO] con-duct: duct 0.19.0.post61+gef60a0e is executing 'kedro run'...
2026-02-10T15:31:53+0000 [INFO] con-duct: Log files will be written to /tmp/duct-kedro2-
[02/10/26 15:31:53] INFO     Kedro is sending anonymous usage data...
                    INFO     Pipeline execution completed successfully in 0.0 sec.
2026-02-10T15:31:53+0000 [INFO] con-duct: Summary:
Exit Code: 0
Command: kedro run
Wall Clock Time: 0.580 sec
Memory Peak Usage (RSS): 9.7 MB
...
[INFO] == Command exit (modification check follows) =====
run(ok): /tmp/telemetry-comparison/kedro-test (dataset) 
         [duct --output-prefix /tmp/duct-kedro2- kedro run]
add(ok): output.txt (file)
save(ok): . (dataset)
```

**Git History (showing provenance):**
```
5877df9 [DATALAD RUNCMD] Execute Kedro with con-duct inside datalad run
a8dd689 Clean up for test 3
9c2d180 [DATALAD RUNCMD] Execute Kedro demo pipeline with DataLad
0b0f491 Clean up for test 2
63354e2 Initialize minimal Kedro project
```

**Benefits of This Combination:**
1. **Kedro telemetry**: Anonymous usage statistics sent to Kedro team
2. **con-duct metrics**: Detailed resource usage stored locally in JSON files
3. **DataLad provenance**: Full command history and file tracking in Git

---

## Comparison Summary

| Feature | Kedro Telemetry | con-duct | DataLad `run` |
|---------|----------------|----------|---------------|
| **Purpose** | Product improvement analytics | Resource monitoring | Provenance tracking |
| **Data Storage** | External (Heap Analytics) | Local JSON files | Git commits |
| **What it tracks** | Project stats, dataset types, events | CPU, memory, runtime, process info | Commands, inputs, outputs |
| **Opt-out** | `KEDRO_DISABLE_TELEMETRY=true` | Don't use duct | Don't use `datalad run` |
| **Privacy** | Anonymous, no personal data | Local only | Local (until you push) |
| **Granularity** | Pipeline/project level | Process level with sampling | Command level |
| **Network Required** | Yes (to send data) | No | No |
| **Integration** | Kedro-specific | Any command | Any command |

## Use Cases

### Use Kedro Telemetry When:
- You want to help improve Kedro
- You're okay with anonymous usage data being sent externally
- You want to track high-level project statistics

### Use con-duct When:
- You need detailed resource usage metrics (CPU, memory)
- You want local-only telemetry (no external services)
- You need to monitor HPC job resources
- You want to track multiple processes and child processes

### Use DataLad `run` When:
- You need reproducible computational provenance
- You want version control for inputs and outputs
- You want to track the exact commands that produced results
- You're building a research pipeline with reproducibility requirements

### Use All Three Together When:
- You want comprehensive telemetry and provenance
- You need both resource monitoring AND command history
- You're doing research with Kedro pipelines
- You want to contribute to Kedro while keeping detailed local logs

## Reproducing This Comparison

The test script used to generate this comparison is available in the repository. To reproduce:

```bash
# Install dependencies
pip install kedro datalad con-duct[all]

# Run the comparison script
bash demo/run_telemetry_comparison.sh
```

Note: The script requires git-annex for full DataLad functionality. In our test environment, git-annex was not available, so some DataLad features were limited, but the core provenance tracking still worked.

## Conclusion

Kedro and con-duct serve complementary purposes:

- **Kedro telemetry** helps the Kedro development team understand usage patterns and improve the product
- **con-duct** provides detailed, local resource usage tracking for individual pipeline runs
- **DataLad** adds reproducibility and provenance tracking on top

Using them together provides the most comprehensive view of your pipeline executions: high-level statistics (Kedro), detailed resource metrics (con-duct), and computational provenance (DataLad).
