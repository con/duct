# Demo: Resource Monitoring Example

This directory contains a demonstration of `duct` and `con-duct` capabilities for monitoring resource usage.

## Contents

- `resource_consumer.py` - A configurable script that simulates various resource consumption patterns (RSS, VSS, CPU)
- `resource_consumer_config.json` - Configuration defining 9 phases of resource consumption over ~4500 seconds
- `example_output_*` - Output files from a duct execution (info.json, usage.json, stdout, stderr)

## Reproducing the Demo Outputs

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
