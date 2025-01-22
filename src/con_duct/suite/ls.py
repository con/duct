import argparse
from collections import OrderedDict
import glob
import json
from typing import List
import pyout  # type: ignore
import yaml
from con_duct.__main__ import DUCT_OUTPUT_PREFIX, SummaryFormatter

VALUE_TRANSFORMATION_MAP = {
    "exit_code": "{value!E}",
    "wall_clock_time": "{value:.3f} sec",
    "peak_rss": "{value!S}",
    "memory_total": "{value!S}",
    "average_rss": "{value!S}",
    "peak_vsz": "{value!S}",
    "average_vsz": "{value!S}",
    "peak_pmem": "{value:.2f!N}%",
    "average_pmem": "{value:.2f!N}%",
    "peak_pcpu": "{value:.2f!N}%",
    "average_pcpu": "{value:.2f!N}%",
    "start_time": "{value:.2f!N}",
    "end_time": "{value:.2f!N}",
}


NON_TRANSFORMED_FIELDS = [
    "hostname",
    "uid",
    "user",
    "gpu",
    "duct_version",
    "schema_version",
    "command",
    "prefix",
    "num_samples",
    "num_reports",
    "stderr",
    "usage",
    "info",
    "prefix",
]

LS_FIELD_CHOICES = list(VALUE_TRANSFORMATION_MAP.keys()) + NON_TRANSFORMED_FIELDS


def load_duct_runs(info_files: List[str]) -> List[dict]:
    loaded = []
    for info_file in info_files:
        with open(info_file) as file:
            loaded.append(json.load(file))
    return loaded


def process_run_data(
    run_data_list: List[str], fields: List[str], formatter
) -> List[OrderedDict]:
    output_rows = []
    for row in run_data_list:
        flattened = _flatten_dict(row)
        restricted = _restrict_row(fields, flattened)
        formatted = _format_row(restricted, formatter)
        output_rows.append(formatted)
    return output_rows


def _flatten_dict(d):
    items = []
    for k, v in d.items():
        if isinstance(v, dict):
            items.extend(_flatten_dict(v).items())
        else:
            items.append((k, v))
    return dict(items)


def _restrict_row(field_list, row):
    restricted = OrderedDict()
    # prefix is the "primary key", its the only field guaranteed to be unique.
    restricted["prefix"] = row["prefix"]
    for k, v in row.items():
        if k in field_list and k != "prefix":
            restricted[k.split(".")[-1]] = v
    return restricted


def _format_row(row, formatter):
    transformed = OrderedDict()
    for col, value in row.items():
        if transformation := VALUE_TRANSFORMATION_MAP.get(col):
            value = formatter.format(transformation, value=value)
        transformed[col] = value
    return transformed


def pyout_ls(run_data_list):
    # Generate Tabular table to output
    table = pyout.Tabular(
        style=dict(
            header_=dict(bold=True, transform=str.upper),
        ),
    )
    for row in run_data_list:
        table(row)


def ls(args: argparse.Namespace) -> int:
    pattern = f"{DUCT_OUTPUT_PREFIX[:DUCT_OUTPUT_PREFIX.index('{')]}*_info.json"
    info_files = glob.glob(pattern)
    run_data_raw = load_duct_runs(info_files)
    formatter = SummaryFormatter(enable_colors=args.colors)
    output_rows = process_run_data(run_data_raw, args.fields, formatter)

    if args.format == "summaries":
        for row in output_rows:
            for col, value in row.items():
                if not col == "prefix":
                    col = f"\t{col}"
                print(f"{col.replace('_', ' ').title()}: {value}")
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
