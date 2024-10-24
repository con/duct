import argparse
import json
from pprint import pprint


def pprint_json(args: argparse.Namespace) -> int:
    """
    Prints the contents of a JSON file using pprint.
    """
    try:
        with open(args.file_path, "r") as file:
            data = json.load(file)
        pprint(data)

    except FileNotFoundError:
        print(f"File not found: {args.file_path}")
        return 1
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return 1

    return 0
