import argparse
import sys
from typing import List, Optional
from con_duct.suite.plot import matplotlib_plot
from con_duct.suite.pprint_json import pprint_json


def execute(args: argparse.Namespace) -> int:
    result = args.func(args)
    if not isinstance(result, int):
        raise TypeError(
            f"Each con-duct subcommand must return an int returncode, got {type(result)}"
        )
    return result


def main(argv: Optional[List[str]] = None) -> None:
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

    # Subcommand: plot
    parser_plot = subparsers.add_parser(
        "plot", help="Plot resource usage for an execution."
    )
    parser_plot.add_argument("file_path", help="duct-produced usage.json file plot.")
    parser_plot.add_argument(
        "--output",
        help="Output path for the png file. If not passed, show the file but do not save.",
        default=None,
    )
    # parser_plot.add_argument(
    #     "-b",
    #     "--backend",
    #     default=DEFAULT_PLOT_BACKEND,
    #     choices=("matplotlib",)
    #     help="which backend to plot with
    # )
    parser_plot.set_defaults(func=matplotlib_plot)

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
    else:
        sys.exit(execute(args))
