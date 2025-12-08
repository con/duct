import argparse
import json
import logging
from pprint import pprint
from typing import Any
from con_duct.duct_main import SummaryFormatter
from con_duct.json_utils import is_jsonl_file, load_info_file, load_usage_file

lgr = logging.getLogger(__name__)


def get_field_conversion_mapping() -> dict[str, str]:
    """
    Map field names to SummaryFormatter conversion types.
    """
    return {
        "average_pcpu": "P",
        "average_pmem": "P",
        "average_rss": "S",
        "average_vsz": "S",
        "peak_pcpu": "P",
        "peak_pmem": "P",
        "peak_rss": "S",
        "peak_vsz": "S",
        "wall_clock_time": "T",
        "start_time": "D",
        "end_time": "D",
    }


def _apply_conversion(
    key: str, value: Any, field_mapping: dict[str, str], formatter: SummaryFormatter
) -> Any:
    """
    Apply SummaryFormatter conversion to a value based on field name.
    """
    if not isinstance(value, (int, float)):
        return value

    conversion = field_mapping.get(key.lower())
    if conversion:
        return formatter.convert_field(str(value), conversion)

    return value


def humanize_data(data: Any, formatter: SummaryFormatter) -> Any:
    """
    Recursively humanize numeric values using SummaryFormatter conversions.
    """
    field_mapping = get_field_conversion_mapping()

    if isinstance(data, dict):
        return {
            key: humanize_data(
                _apply_conversion(key, value, field_mapping, formatter), formatter
            )
            for key, value in data.items()
        }
    elif isinstance(data, list):
        return [humanize_data(item, formatter) for item in data]
    else:
        return data


def pprint_json(args: argparse.Namespace) -> int:
    """
    Prints the contents of a JSON file using pprint.

    Handles both standard JSON files and JSON Lines (usage.jsonl) files.
    """
    try:
        if is_jsonl_file(args.file_path):
            data: Any = load_usage_file(args.file_path)
        else:
            data = load_info_file(args.file_path)

        if args.humanize:
            formatter = SummaryFormatter()
            data = humanize_data(data, formatter)

        pprint(data)

    except FileNotFoundError:
        lgr.error("File not found: %s", args.file_path)
        return 1
    except json.JSONDecodeError as e:
        lgr.error("Error decoding JSON: %s", e)
        return 1

    return 0
