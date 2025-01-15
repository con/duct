import argparse
import glob
import json
from typing import List
import pyout
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


def load_duct_runs(info_files: List[str]) -> List[dict]:
    loaded = []
    for info_file in info_files:
        with open(info_file) as file:
            loaded.append(json.load(file))
    return loaded


def _flatten_dict(d, parent_key="", sep="."):
    """Flatten a nested dictionary, creating keys as dot-separated paths."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def _restrict_row(include_only, row):
    restricted = {}
    for k, v in row.items():
        if k in include_only:
            restricted[k.split(".")[-1]] = v
    return restricted


def pyout_ls(run_data_list):
    # Generate Tabular table to output
    table = pyout.Tabular(
        style=dict(
            header_=dict(bold=True, transform=str.upper),
            # Default styling could be provided from some collection of styling files
            default_=dict(
                color=dict(
                    lookup={
                        "Trix": "green",
                        "110": "red",
                        "100": "green",  # since no grey for now
                    }
                )
            ),
        ),
    )
    include_only = ["command", "execution_summary.exit_code"]
    for row in run_data_list:
        # table(row)
        flattened = _flatten_dict(row)
        table(_restrict_row(include_only, flattened))


def ls(args: argparse.Namespace) -> int:
    pattern = f"{DUCT_OUTPUT_PREFIX[:DUCT_OUTPUT_PREFIX.index('{')]}*_info.json"
    info_files = glob.glob(pattern)
    run_data_list = load_duct_runs(info_files)
    if args.format == "summaries":
        formatter = SummaryFormatter()  # TODO enable_colors=self.colors)
        for data in run_data_list:
            print(formatter.format(LS_SUMMARY_FORMAT, **data))
    elif args.format == "pyout":
        pyout_ls(run_data_list)
    elif args.format == "json":
        print(json.dumps(run_data_list))
    elif args.format == "json_pp":
        print(json.dumps(run_data_list, indent=True))
    elif args.format == "yaml":
        print(yaml.dump(run_data_list, default_flow_style=False))
    else:
        raise RuntimeError(
            f"Unexpected format encountered: {args.format}. This should have been caught by argparse.",
        )
    return 0
