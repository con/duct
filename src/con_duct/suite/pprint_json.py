import argparse
from datetime import datetime
import json
from pprint import pprint
from typing import Any, Union
from con_duct.__main__ import SummaryFormatter


def humanize_value(
    key: str, value: Any, formatter: SummaryFormatter
) -> Union[str, Any]:
    """
    Convert numeric values to human-readable formats based on field names.
    """
    if not isinstance(value, (int, float)):
        return value

    # CPU percentage fields
    if "cpu" in key.lower() or "pcpu" in key.lower():
        return f"{value:.2f}%"

    # Memory fields (convert bytes to human-readable format)
    if any(mem_field in key.lower() for mem_field in ["rss", "memory", "mem", "vsz"]):
        return formatter.naturalsize(value)

    # Duration fields - only wall_clock_time for now
    if key.lower() == "wall_clock_time":
        if value >= 3600:  # >= 1 hour
            hours = int(value // 3600)
            minutes = int((value % 3600) // 60)
            seconds = value % 60
            return f"{hours}h {minutes}m {seconds:.1f}s"
        elif value >= 60:  # >= 1 minute
            minutes = int(value // 60)
            seconds = value % 60
            return f"{minutes}m {seconds:.1f}s"
        else:
            return f"{value:.2f}s"

    # Start/end time fields (convert Unix timestamps to readable format)
    if any(field in key.lower() for field in ["start_time", "end_time"]) and isinstance(
        value, (int, float)
    ):
        try:
            dt = datetime.fromtimestamp(value)
            return dt.strftime("%b %d, %Y %I:%M %p")
        except (ValueError, OSError):
            # If parsing fails, return original value
            return value

    return value


def humanize_data(data: Any, formatter: SummaryFormatter) -> Any:
    """
    Recursively humanize numeric values in data structure.
    """
    if isinstance(data, dict):
        return {
            key: humanize_data(humanize_value(key, value, formatter), formatter)
            for key, value in data.items()
        }
    elif isinstance(data, list):
        return [humanize_data(item, formatter) for item in data]
    else:
        return data


def pprint_json(args: argparse.Namespace) -> int:
    """
    Prints the contents of a JSON file using pprint.
    """
    try:
        with open(args.file_path, "r") as file:
            data = json.load(file)

        if args.humanize:
            formatter = SummaryFormatter()
            data = humanize_data(data, formatter)

        pprint(data)

    except FileNotFoundError:
        print(f"File not found: {args.file_path}")
        return 1
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return 1

    return 0
