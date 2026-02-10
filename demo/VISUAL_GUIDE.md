# Visual Guide: Kedro vs con-duct Telemetry

## Side-by-Side Comparison

### Running Kedro Alone

```bash
$ kedro run
```

**What you see:**
```
INFO     Kedro is sending anonymous usage data...
DEBUG    Failed to send data to Heap.
INFO     Pipeline execution completed successfully in 0.0 sec.
```

**What happens:**
- Kedro tries to send anonymous usage data to Heap Analytics
- Your pipeline executes normally
- No local telemetry files are created

---

### Running Kedro with con-duct

```bash
$ duct --output-prefix /tmp/my-kedro-run- kedro run
```

**What you see:**
```
[INFO] con-duct: duct 0.19.0 is executing 'kedro run'...
[INFO] con-duct: Log files will be written to /tmp/my-kedro-run-

INFO     Kedro is sending anonymous usage data...
DEBUG    Failed to send data to Heap.
INFO     Pipeline execution completed successfully in 0.0 sec.

[INFO] con-duct: Summary:
Exit Code: 0
Command: kedro run
Wall Clock Time: 0.579 sec
Memory Peak Usage (RSS): 9.7 MB
Average CPU Usage: 0.00%
```

**What happens:**
- con-duct wraps your kedro command
- Kedro still tries to send its telemetry
- con-duct monitors resource usage
- 4 files are created:

```
/tmp/my-kedro-run-info.json      # System info + execution summary
/tmp/my-kedro-run-usage.jsonl    # Time-series resource data
/tmp/my-kedro-run-stdout         # Captured stdout
/tmp/my-kedro-run-stderr         # Captured stderr
```

---

### Example: What's in the con-duct files?

#### info.json
```json
{
    "command": "kedro run",
    "system": {
        "cpu_total": 4,
        "memory_total": 16771862528,
        "hostname": "myserver"
    },
    "execution_summary": {
        "exit_code": 0,
        "wall_clock_time": 0.5795,
        "peak_rss": 9682944,
        "average_rss": 9682944,
        "peak_pcpu": 0.0
    }
}
```

#### usage.jsonl
```json
{
    "timestamp": "2026-02-10T15:31:53.390237+00:00",
    "processes": {
        "4864": {
            "pcpu": 0.0,
            "pmem": 0.0,
            "rss": 9682944,
            "cmd": "/usr/bin/python3 /home/runner/.local/bin/kedro run"
        }
    },
    "totals": {
        "rss": 9682944,
        "pcpu": 0.0
    }
}
```

---

## When to Use What?

### Use Kedro telemetry when:
✅ You want to help improve Kedro  
✅ You're okay with anonymous data being sent externally  
✅ You don't need detailed resource metrics

### Use con-duct when:
✅ You need CPU and memory usage data  
✅ You want all data stored locally  
✅ You're tracking HPC job resources  
✅ You want detailed provenance information

### Use both together when:
✅ You want to contribute to Kedro AND track resources  
✅ You're doing research and need comprehensive metrics  
✅ You want both high-level stats and detailed monitoring

---

## Quick Reference: File Locations

| Tool | Data Location | What's Stored |
|------|---------------|---------------|
| **Kedro** | Heap Analytics (external) | Anonymous project stats, pipeline info |
| **con-duct** | Local files (`*-info.json`, `*-usage.jsonl`) | Resource metrics, system info, stdout/stderr |
| **DataLad** | Git commits | Command provenance, input/output tracking |

---

## Try It Yourself

1. **Install dependencies:**
   ```bash
   pip install kedro con-duct[all]
   ```

2. **Run the demo script:**
   ```bash
   cd demo
   ./run_telemetry_comparison.sh
   ```

3. **Read the full comparison:**
   ```bash
   cat demo/telemetry_comparison_kedro.md
   ```

---

## Visual: Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                      $ kedro run                             │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ├─► Kedro Telemetry ──► Heap Analytics (external)
                   │   • Project statistics
                   │   • Dataset types
                   │   • Pipeline events
                   │
                   └─► Your Pipeline ──► Results/Outputs


┌─────────────────────────────────────────────────────────────┐
│              $ duct --output-prefix logs/ kedro run          │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ├─► Kedro Telemetry ──► Heap Analytics (external)
                   │   • Project statistics
                   │   • Dataset types
                   │
                   ├─► con-duct Monitoring ──► Local JSON files
                   │   • logs/info.json (summary)
                   │   • logs/usage.jsonl (time series)
                   │   • logs/stdout (console output)
                   │   • logs/stderr (error output)
                   │
                   └─► Your Pipeline ──► Results/Outputs
```

---

## Key Takeaway

**Kedro and con-duct are complementary, not competing:**

- **Kedro telemetry** helps the Kedro team improve the product
- **con-duct** helps YOU understand your pipeline's resource usage
- **Together**, they provide comprehensive insights into your workflows

Both can be active simultaneously without conflict!
