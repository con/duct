# Demo: Resource Monitoring Example

This directory contains demonstrations of `duct` and `con-duct` capabilities.

## Contents

### Resource Monitoring Demo

- `resource_consumer.py` - A configurable script that simulates various resource consumption patterns (RSS, VSS, CPU)
- `resource_consumer_config.json` - Configuration defining 9 phases of resource consumption over ~4500 seconds
- `example_output_*` - Output files from a duct execution (info.json, usage.json, stdout, stderr)

### Telemetry Comparison Demo

- `telemetry_comparison_kedro.md` - Comprehensive comparison of telemetry collected by Kedro vs con-duct
- `run_telemetry_comparison.sh` - Script to reproduce the telemetry comparison

## Reproducing the Resource Monitoring Demo

### Step 1: Generate monitoring data

Run the resource consumer under duct monitoring:

```bash
duct --r-i 20 -p demo/example_output_ ./demo/resource_consumer.py --config demo/resource_consumer_config.json
```

This will:
- Execute the resource consumer with the config phases
- Sample resource usage every second (default)
- Report aggregated data every 20 seconds (`--r-i 20`)
- Write output files with prefix `demo/example_output_`

### Step 2: View the plot

Create a visualization from the usage data:

```bash
con-duct plot demo/example_output_usage.json
```

This displays an interactive plot showing RSS, VSS, and CPU usage over time.

## Reproducing the Telemetry Comparison

The telemetry comparison demonstrates how con-duct's telemetry differs from and complements Kedro's telemetry, and how both can work together with DataLad for provenance tracking.

### Prerequisites

```bash
pip install kedro datalad con-duct[all]
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

### Run the comparison

```bash
cd demo
./run_telemetry_comparison.sh
```

This will create a test directory and run four tests:
1. Kedro with telemetry enabled (baseline)
2. Kedro with DataLad provenance tracking
3. Kedro with con-duct resource monitoring
4. All three combined (Kedro + DataLad + con-duct)

See `telemetry_comparison_kedro.md` for the full comparison results and analysis.
