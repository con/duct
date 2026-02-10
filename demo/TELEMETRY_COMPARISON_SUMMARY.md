# Quick Summary: Kedro vs con-duct Telemetry

This is a summary of the full telemetry comparison available in `telemetry_comparison_kedro.md`.

## Key Differences

### Kedro Telemetry
- **Purpose**: Anonymous product improvement analytics
- **Data sent to**: Heap Analytics (external service)
- **What it tracks**: Project statistics, pipeline info, dataset types
- **Opt-out**: Set `KEDRO_DISABLE_TELEMETRY=true`

Example output:
```
INFO     Kedro is sending anonymous usage data with the sole purpose 
         of improving the product. No personal data or IP addresses 
         are stored on our side.
DEBUG    Failed to send data to Heap. Exception of type 
         'ConnectionError' was raised.
```

### con-duct Telemetry
- **Purpose**: Resource usage monitoring and provenance tracking
- **Data stored**: Locally in JSON files
- **What it tracks**: CPU, memory (RSS/VSZ), wall clock time, process details
- **Opt-out**: Don't use `duct` wrapper

Example output:
```
con-duct: Summary:
Exit Code: 0
Command: kedro run
Wall Clock Time: 0.579 sec
Memory Peak Usage (RSS): 9.7 MB
Memory Average Usage (RSS): 9.7 MB
CPU Peak Usage: 0.00%
```

Files created:
- `*-info.json` - System info and execution summary
- `*-usage.jsonl` - Detailed resource usage samples over time
- `*-stdout` - Captured stdout
- `*-stderr` - Captured stderr

## Working Together

You can use both at the same time:

```bash
# Run kedro with con-duct monitoring (both telemetries active)
duct --output-prefix /tmp/my-run- kedro run
```

Add DataLad for provenance tracking:

```bash
# All three: DataLad provenance + con-duct metrics + Kedro telemetry
datalad run --output results/ duct --output-prefix logs/ kedro run
```

This gives you:
1. **Kedro**: Anonymous usage stats sent to Kedro team
2. **con-duct**: Local resource usage metrics in JSON
3. **DataLad**: Command provenance in Git history

## Comparison Table

| Feature | Kedro | con-duct | DataLad |
|---------|-------|----------|---------|
| Data location | External | Local | Git |
| Resource metrics | ❌ | ✅ CPU, memory | ❌ |
| Command tracking | ❌ | ✅ Command string | ✅ Full command |
| File provenance | ❌ | ❌ | ✅ Inputs/outputs |
| Network required | ✅ | ❌ | ❌ |
| Privacy | Anonymous | Local only | Local |

## See Full Comparison

For detailed test results, example outputs, and JSON structures, see:
- **Full documentation**: `telemetry_comparison_kedro.md`
- **Reproduction script**: `run_telemetry_comparison.sh`
