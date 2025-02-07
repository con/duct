import argparse
from collections import OrderedDict
import glob
import json
import logging
from typing import Any, Dict, List, Optional
from packaging.version import Version

try:
    import pyout  # type: ignore
except ImportError:
    pyout = None
import yaml
from con_duct.__main__ import DUCT_OUTPUT_PREFIX, SummaryFormatter

lgr = logging.getLogger(__name__)

VALUE_TRANSFORMATION_MAP: Dict[str, str] = {
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

NON_TRANSFORMED_FIELDS: List[str] = [
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

LS_FIELD_CHOICES: List[str] = (
    list(VALUE_TRANSFORMATION_MAP.keys()) + NON_TRANSFORMED_FIELDS
)
MINIMUM_SCHEMA_VERSION: str = "0.2.0"


def load_duct_runs(info_files: List[str]) -> List[Dict[str, Any]]:
    loaded: List[Dict[str, Any]] = []
    for info_file in info_files:
        with open(info_file) as file:
            try:
                this: Dict[str, Any] = json.load(file)
                # this["prefix"] is the path at execution time, could have moved
                this["prefix"] = info_file.split("info.json")[0]
                if Version(this["schema_version"]) >= Version(MINIMUM_SCHEMA_VERSION):
                    loaded.append(this)
                else:
                    # TODO lower log level once --log-level is respected
                    lgr.warning(
                        f"Skipping {this['prefix']}, schema version {this['schema_version']} "
                        f"is below minimum schema version {MINIMUM_SCHEMA_VERSION}."
                    )
            except Exception as exc:
                lgr.warning("Failed to load file %s: %s", file, exc)
    return loaded


def process_run_data(
    run_data_list: List[Dict[str, Any]], fields: List[str], formatter: SummaryFormatter
) -> List[OrderedDict[str, Any]]:
    output_rows: List[OrderedDict[str, Any]] = []
    for row in run_data_list:
        flattened = _flatten_dict(row)
        try:
            restricted = _restrict_row(fields, flattened)
        except KeyError:
            lgr.warning(
                "Failed to pick fields of interest from a record, skipping. Record was: %s",
                list(flattened),
            )
            continue
        formatted = _format_row(restricted, formatter)
        output_rows.append(formatted)
    return output_rows


def _flatten_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    items: List[tuple[str, Any]] = []
    for k, v in d.items():
        if isinstance(v, dict):
            items.extend(_flatten_dict(v).items())
        else:
            items.append((k, v))
    return dict(items)


def _restrict_row(field_list: List[str], row: Dict[str, Any]) -> OrderedDict[str, Any]:
    restricted: OrderedDict[str, Any] = OrderedDict()
    # prefix is the "primary key", its the only field guaranteed to be unique.
    restricted["prefix"] = row["prefix"]
    for field in field_list:
        if field != "prefix" and field in row:
            restricted[field.split(".")[-1]] = row[field]
    return restricted


def _format_row(
    row: OrderedDict[str, Any], formatter: SummaryFormatter
) -> OrderedDict[str, Any]:
    transformed: OrderedDict[str, Any] = OrderedDict()
    for col, value in row.items():
        transformation: Optional[str] = VALUE_TRANSFORMATION_MAP.get(col)
        if transformation is not None:
            value = formatter.format(transformation, value=value)
        transformed[col] = value
    return transformed


def pyout_ls(run_data_list: List[OrderedDict[str, Any]]) -> None:
    """Generate and print a tabular table using pyout."""
    if pyout is None:
        raise RuntimeError("pyout is required for this output format.")

    with pyout.Tabular(
        style=dict(
            header_=dict(bold=True, transform=str.upper),
        ),
        mode="final",
    ) as table:
        for row in run_data_list:
            table(row)


def ls(args: argparse.Namespace) -> int:

    if not args.paths:
        pattern = f"{DUCT_OUTPUT_PREFIX[:DUCT_OUTPUT_PREFIX.index('{')]}*"
        args.paths = [p for p in glob.glob(pattern)]

    info_files = [path for path in args.paths if path.endswith("info.json")]
    run_data_raw = load_duct_runs(info_files)
    formatter = SummaryFormatter(enable_colors=args.colors)
    output_rows = process_run_data(run_data_raw, args.fields, formatter)

    if args.format == "auto":
        args.format = "summaries" if pyout is None else "pyout"

    if args.format == "summaries":
        for row in output_rows:
            for col, value in row.items():
                if not col == "prefix":
                    col = f"\t{col}"
                print(f"{col.replace('_', ' ').title()}: {value}")
    elif args.format == "pyout":
        if pyout is None:
            raise RuntimeError("Install pyout for pyout output")
        pyout_ls(output_rows)
    elif args.format == "json":
        print(json.dumps(output_rows))
    elif args.format == "json_pp":
        print(json.dumps(output_rows, indent=2))
    elif args.format == "yaml":
        plain_rows = [dict(row) for row in output_rows]
        print(yaml.dump(plain_rows, default_flow_style=False))
    else:
        raise RuntimeError(
            f"Unexpected format encountered: {args.format}. This should have been caught by argparse.",
        )
    return 0
