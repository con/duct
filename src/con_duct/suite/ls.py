import argparse
from collections import OrderedDict
import glob
import json
import logging
import re
from types import ModuleType
from typing import Any, Dict, List, Optional
from con_duct.__main__ import DUCT_OUTPUT_PREFIX, SummaryFormatter
from con_duct.utils import parse_version

try:
    import pyout  # type: ignore
except ImportError:
    pyout = None

try:
    import yaml
except ImportError:
    yaml: Optional[ModuleType] = None  # type: ignore


lgr = logging.getLogger(__name__)

VALUE_TRANSFORMATION_MAP: Dict[str, str] = {
    "average_pcpu": "{value:.2f!N}%",
    "average_pmem": "{value:.2f!N}%",
    "average_rss": "{value!S}",
    "average_vsz": "{value!S}",
    "end_time": "{value:.2f!N}",
    "exit_code": "{value!E}",
    "memory_total": "{value!S}",
    "peak_pcpu": "{value:.2f!N}%",
    "peak_pmem": "{value:.2f!N}%",
    "peak_rss": "{value!S}",
    "peak_vsz": "{value!S}",
    "start_time": "{value:.2f!N}",
    "wall_clock_time": "{value:.3f} sec",
}

NON_TRANSFORMED_FIELDS: List[str] = [
    "command",
    "cpu_total",
    "duct_version",
    "gpu",
    "hostname",
    "info",
    "logs_prefix",
    "num_samples",
    "num_reports",
    "prefix",
    "schema_version",
    "stderr",
    "stdout",
    "uid",
    "usage",
    "user",
    "working_directory",
]

LS_FIELD_CHOICES: List[str] = (
    list(VALUE_TRANSFORMATION_MAP.keys()) + NON_TRANSFORMED_FIELDS
)
MINIMUM_SCHEMA_VERSION: str = "0.2.1"


def load_duct_runs(
    info_files: List[str], eval_filter: Optional[str] = None
) -> List[Dict[str, Any]]:
    loaded: List[Dict[str, Any]] = []
    for info_file in info_files:
        with open(info_file) as file:
            try:
                this: Dict[str, Any] = json.load(file)
                # this["prefix"] is the path at execution time, could have moved
                this["prefix"] = info_file.split("info.json")[0]
                if parse_version(this["schema_version"]) < parse_version(
                    MINIMUM_SCHEMA_VERSION
                ):
                    lgr.debug(
                        f"Skipping {this['prefix']}, schema version {this['schema_version']} "
                        f"is below minimum schema version {MINIMUM_SCHEMA_VERSION}."
                    )
                    continue
                if eval_filter is not None and not (
                    eval_results := eval(eval_filter, _flatten_dict(this), dict(re=re))
                ):
                    lgr.debug(
                        "Filtering out %s due to filter results matching: %s",
                        this,
                        eval_results,
                    )
                    continue

                loaded.append(this)
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


def pyout_ls(run_data_list: List[OrderedDict[str, Any]], enable_colors: bool) -> None:
    """Generate and print a tabular table using pyout."""
    if pyout is None:
        raise RuntimeError("pyout is required for this output format.")

    color_styles = {
        "E": dict(
            color=dict(
                re_lookup=[
                    ["^0$", "green"],  # if exactly "0", then green
                    [".*", "red"],  # anything else gets red
                ]
            )
        ),
        "N": dict(
            color=dict(
                re_lookup=[
                    [f"^{SummaryFormatter.NONE}", "red"],  # if starts with NONE
                    [".*", "green"],
                ]
            )
        ),
    }
    # S is humansize, conversion done, coloring same as N
    color_styles["S"] = color_styles["N"]

    pattern = re.compile(r"!([A-Z])")
    conversion_map = (
        {
            k: color_styles[match.group(1)]
            for k, v in VALUE_TRANSFORMATION_MAP.items()
            if (match := pattern.search(v))
        }
        if enable_colors
        else {}
    )
    with pyout.Tabular(
        style=dict(
            header_=dict(bold=True, transform=str.upper),
            **conversion_map,
        ),
        mode="final",
    ) as table:
        for row in run_data_list:
            table(row)


def ls(args: argparse.Namespace) -> int:
    if not args.paths:
        pattern = f"{DUCT_OUTPUT_PREFIX[:DUCT_OUTPUT_PREFIX.index('{')]}*"
        args.paths = [p for p in glob.glob(pattern)]

    if args.format == "auto":
        args.format = "summaries" if pyout is None else "pyout"

    formatter = SummaryFormatter(
        enable_colors=False if args.format == "pyout" else args.colors
    )
    info_files = [path for path in args.paths if path.endswith("info.json")]
    run_data_raw = load_duct_runs(info_files, args.eval_filter)
    output_rows = process_run_data(run_data_raw, args.fields, formatter)

    if args.format == "summaries":
        for row in output_rows:
            for col, value in row.items():
                if not col == "prefix":
                    col = f"\t{col}"
                print(f"{col.replace('_', ' ').title()}: {value}")
    elif args.format == "pyout":
        if pyout is None:
            raise RuntimeError("Install pyout for pyout output")
        pyout_ls(output_rows, args.colors)
    elif args.format == "json":
        print(json.dumps(output_rows))
    elif args.format == "json_pp":
        print(json.dumps(output_rows, indent=2))
    elif args.format == "yaml":
        if yaml is None:
            raise RuntimeError("Install PyYaml yaml output")
        plain_rows = [dict(row) for row in output_rows]
        print(yaml.dump(plain_rows, default_flow_style=False))
    else:
        raise RuntimeError(
            f"Unexpected format encountered: {args.format}. This should have been caught by argparse.",
        )
    return 0
