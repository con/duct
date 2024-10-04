import argparse
import json
from pprint import pprint
import sys


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


def execute(args: argparse.Namespace) -> int:
    result = args.func(args)
    if not isinstance(result, int):
        raise TypeError(
            f"Each con-duct subcommand must return an int returncode, got {type(result)}"
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="con-duct",
        description="A command-line tool for managing various tasks.",
        usage="con-duct <command> [options]",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Subcommand: pp
    parser_pp = subparsers.add_parser("pp", help="Pretty print a JSON log")
    parser_pp.add_argument("file_path", help="JSON file to pretty print")
    parser_pp.set_defaults(func=pprint_json)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
    else:
        sys.exit(execute(args))
