import argparse
import glob
import json
import yaml
from con_duct.__main__ import DUCT_OUTPUT_PREFIX, SummaryFormatter

LS_SUMMARY_FORMAT = (
    "Command: {command}\n"
    "\tWall Clock Time: {execution_summary[wall_clock_time]:.3f} sec\n"
    "\tMemory Peak Usage (RSS): {execution_summary[peak_rss]!S}\n"
    "\tVirtual Memory Peak Usage (VSZ): {execution_summary[peak_vsz]!S}\n"
    "\tMemory Peak Percentage: {execution_summary[peak_pmem]:.2f!N}%\n"
    "\tCPU Peak Usage: {execution_summary[peak_pcpu]:.2f!N}%\n"
)


def load_duct_runs(info_files):
    loaded = []
    for info_file in info_files:
        with open(info_file) as file:
            loaded.append(json.load(file))
    return loaded


def ls(args: argparse.Namespace) -> int:
    pattern = f"{DUCT_OUTPUT_PREFIX[:DUCT_OUTPUT_PREFIX.index('{')]}*_info.json"
    info_files = glob.glob(pattern)
    run_data_list = load_duct_runs(info_files)
    if args.format == "summaries":
        formatter = SummaryFormatter()  # TODO enable_colors=self.colors)
        for data in run_data_list:
            print(formatter.format(LS_SUMMARY_FORMAT, **data))
        return 0
    if args.format == "json":
        print(json.dumps(run_data_list))
        return 0
    if args.format == "jsonpp":
        print(json.dumps(run_data_list, indent=True))
        return 0
    if args.format == "yaml":
        print(yaml.dump(run_data_list, default_flow_style=False))
        return 0
