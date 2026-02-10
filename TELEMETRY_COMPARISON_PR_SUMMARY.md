# Summary of Changes: Kedro vs con-duct Telemetry Comparison

This PR addresses issue #XXX about comparing telemetry collected by Kedro vs con-duct.

## What Was Done

Following the instructions in the issue, I:

1. **Followed the tutorial** from datalad-handbook PR #1282 (https://github.com/datalad-handbook/book/pull/1282/changes)
2. **Ran the script WITHOUT disabling Kedro telemetry** (unlike the PR which disabled it)
3. **Added con-duct monitoring** around the Kedro invocation
4. **Documented the comparison** showing what each tool collects

## Files Added

### Documentation
- **`demo/telemetry_comparison_kedro.md`** (11KB) - Comprehensive comparison with:
  - Test results from 4 scenarios (Kedro alone, with DataLad, with con-duct, all three)
  - Complete output examples showing both telemetries active
  - Detailed explanation of what each tool collects
  - JSON structure examples from con-duct
  - Comparison tables
  
- **`demo/TELEMETRY_COMPARISON_SUMMARY.md`** (2.5KB) - Quick reference guide with:
  - Key differences table
  - When to use each tool
  - Quick commands
  
- **`demo/VISUAL_GUIDE.md`** (5.6KB) - Visual side-by-side comparison with:
  - Command outputs shown side by side
  - Data flow diagrams
  - Example JSON structures
  - Quick reference tables

### Executable
- **`demo/run_telemetry_comparison.sh`** (4.1KB) - Reproduction script that:
  - Creates a minimal Kedro project
  - Runs 4 test scenarios
  - Shows Kedro telemetry, con-duct metrics, and DataLad provenance

### Updates
- **`demo/README.md`** - Updated to include telemetry comparison section
- **`README.md`** - Added "Examples and Demos" section referencing the comparison

## Key Findings

### Kedro Telemetry
- **Purpose**: Anonymous product improvement analytics
- **Sends to**: Heap Analytics (external service)
- **Collects**: Project stats, dataset types, pipeline events
- **Opt-out**: `KEDRO_DISABLE_TELEMETRY=true`

### con-duct Telemetry
- **Purpose**: Resource usage monitoring and provenance
- **Stores**: Local JSON files
- **Collects**: CPU, memory (RSS/VSZ), wall time, process details
- **Opt-out**: Don't use the `duct` wrapper

### They Work Together!
The comparison demonstrates that both telemetries can run simultaneously without conflict:
```bash
$ duct --output-prefix logs/ kedro run
```

Results in:
- Kedro sends its anonymous usage data to Heap (for product improvement)
- con-duct captures detailed resource metrics locally (for your analysis)
- Both telemetries provide complementary insights

## How to Use

```bash
# Install dependencies
pip install kedro datalad con-duct[all]

# Run the comparison
cd demo
./run_telemetry_comparison.sh

# Read the results
cat telemetry_comparison_kedro.md
```

## Potential Use for datalad-handbook PR

The comparison document can be used to add a telemetry/provenance section to the datalad-handbook PR #1282. It shows:

1. **What Kedro collects** (when telemetry is enabled)
2. **What con-duct adds on top** (resource metrics)
3. **How DataLad complements both** (provenance tracking)

The key insight is that these three tools serve complementary purposes and can all work together:
- **Kedro**: High-level project analytics (helps Kedro team)
- **con-duct**: Detailed resource tracking (helps you optimize)
- **DataLad**: Computational provenance (helps reproducibility)

## Testing

All tests were run successfully:
- Test 1: Kedro with telemetry enabled ✅
- Test 2: Kedro with DataLad run ✅
- Test 3: Kedro with con-duct ✅
- Test 4: All three combined ✅

The script is fully reproducible and includes all necessary setup code.
