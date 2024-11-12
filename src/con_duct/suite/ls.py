import argparse
import glob
import json
from pprint import pprint
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
# "Log files location: {logs_prefix}\n"
#     "Memory Peak Usage (RSS): {peak_rss!S}\n"
#     "Memory Average Usage (RSS): {average_rss!S}\n"
#     "Virtual Memory Peak Usage (VSZ): {peak_vsz!S}\n"
#     "Virtual Memory Average Usage (VSZ): {average_vsz!S}\n"
#     "Memory Peak Percentage: {peak_pmem:.2f!N}%\n"
#     "Memory Average Percentage: {average_pmem:.2f!N}%\n"
#     "CPU Peak Usage: {peak_pcpu:.2f!N}%\n"
#     "Average CPU Usage: {average_pcpu:.2f!N}%\n"
#


def ls(args: argparse.Namespace) -> int:
    pattern = f"{DUCT_OUTPUT_PREFIX[:DUCT_OUTPUT_PREFIX.index('{')]}*_info.json"
    duct_runs = glob.glob(pattern)
    if args.format == "summaries":
        formatter = SummaryFormatter()  # TODO enable_colors=self.colors)
        for info_file in duct_runs:
            with open(info_file) as file:
                data = json.loads(file.read())
                # print(json.dumps(data))
                print(formatter.format(LS_SUMMARY_FORMAT, **data))
        return 0
    if args.format == "json":
        for info_file in duct_runs:
            with open(info_file) as file:
                print(file.read())
        return 0
    if args.format == "jsonpp":
        for info_file in duct_runs:
            with open(info_file, "r") as file:
                data = json.load(file)
            pprint(data)
        return 0
    if args.format == "yaml":
        for info_file in duct_runs:
            with open(info_file) as file:
                data = json.load(file)
                print(yaml.dump(data, default_flow_style=False))
        return 0
