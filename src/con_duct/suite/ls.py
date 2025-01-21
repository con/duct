import argparse
from collections import OrderedDict
import glob
import json
from typing import List
import pyout  # type: ignore
import yaml
from con_duct.__main__ import DUCT_OUTPUT_PREFIX, SummaryFormatter

LS_SUMMARY_FORMAT = {
    "prefix": "Prefix: {value}",
    "command": "\tCommand: {value}",
    "exit_code": "\tExit Code {value!E}",
    "wall_clock_time": "\tWall Clock Time: {value:.3f} sec",
    "peak_rss": "\tMemory Peak Usage (RSS): {value!S}",
}


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


def _restrict_row(field_list, row):
    restricted = OrderedDict()
    for k, v in row.items():
        # output_paths.prefix is the unique key
        if k in field_list or k == "output_paths.prefix":
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
    for row in run_data_list:
        # moves to first column, which is unique key.
        row.move_to_end("prefix", last=False)
        table(row)


def ls(args: argparse.Namespace) -> int:
    pattern = f"{DUCT_OUTPUT_PREFIX[:DUCT_OUTPUT_PREFIX.index('{')]}*_info.json"
    info_files = glob.glob(pattern)
    run_data_list = load_duct_runs(info_files)
    output_rows = []
    for row in run_data_list:
        flattened = _flatten_dict(row)
        output_rows.append(_restrict_row(args.fields, flattened))

    if args.format == "summaries":
        formatter = SummaryFormatter()  # TODO enable_colors=self.colors)
        for row in output_rows:
            for col, value in row.items():
                print(formatter.format(LS_SUMMARY_FORMAT[col], value=value))
    elif args.format == "pyout":
        pyout_ls(output_rows)
    elif args.format == "json":
        print(json.dumps(output_rows))
    elif args.format == "json_pp":
        print(json.dumps(output_rows, indent=True))
    elif args.format == "yaml":
        print(yaml.dump(output_rows, default_flow_style=False))
    else:
        raise RuntimeError(
            f"Unexpected format encountered: {args.format}. This should have been caught by argparse.",
        )
    return 0
