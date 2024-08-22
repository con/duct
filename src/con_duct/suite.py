import argparse
import json
from pprint import pprint


def pprint_json(args):
    """
    Prints the contents of a JSON file using pprint.
    """
    try:
        with open(args.file_path, "r") as file:
            data = json.load(file)
        pprint(data)

    except FileNotFoundError:
        print(f"File not found: {args.file_path}")
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")


def main():
    parser = argparse.ArgumentParser(
        prog="con-duct",
        description="A command-line tool for managing various tasks.",
        usage="con-duct <command> [options]",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Subcommand: pp
    parser_pp = subparsers.add_parser("pp", help="Pretty print a log")
    parser_pp.add_argument("file_path", help="File to pretty print")
    parser_pp.set_defaults(func=pprint_json)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
    else:
        args.func(args)
