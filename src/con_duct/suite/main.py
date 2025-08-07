import argparse
import logging
import os
import sys
from typing import List, Optional
from con_duct import __version__
from con_duct.suite.ls import LS_FIELD_CHOICES, ls
from con_duct.suite.plot import matplotlib_plot
from con_duct.suite.pprint_json import pprint_json

lgr = logging.getLogger("con-duct")
DEFAULT_LOG_LEVEL = os.environ.get("DUCT_LOG_LEVEL", "INFO").upper()


def execute(args: argparse.Namespace) -> int:

    if args.log_level == "NONE":
        logging.disable(logging.CRITICAL)
    else:
        logging.basicConfig(level=args.log_level)

    result = args.func(args)
    if not isinstance(result, int):
        raise TypeError(
            f"Each con-duct subcommand must return an int returncode, got {type(result)}"
        )
    return result


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        prog="con-duct",
        description="A suite of commands to manage or manipulate con-duct logs.",
        usage="con-duct <command> [options]",
    )
    parser.add_argument(
        "-l",
        "--log-level",
        default=DEFAULT_LOG_LEVEL,
        choices=("NONE", "CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"),
        type=str.upper,
        help="Level of log output to stderr, use NONE to entirely disable.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Subcommand: pp
    parser_pp = subparsers.add_parser("pp", help="Pretty print a JSON log.")
    parser_pp.add_argument("file_path", help="JSON file to pretty print.")
    parser_pp.add_argument(
        "-H",
        "--humanize",
        action="store_true",
        help="Convert numeric values to human-readable format",
    )
    parser_pp.set_defaults(func=pprint_json)

    # Subcommand: plot
    parser_plot = subparsers.add_parser(
        "plot", help="Plot resource usage for an execution."
    )
    parser_plot.add_argument("file_path", help="duct-produced usage.json file.")
    parser_plot.add_argument(
        "--output",
        help="Output path for the image file. If not specified, plot will be shown and not saved.",
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

    parser_ls = subparsers.add_parser(
        "ls",
        help="Print execution information for all matching runs.",
    )
    parser_ls.add_argument(
        "-f",
        "--format",
        choices=("auto", "pyout", "summaries", "json", "json_pp", "yaml"),
        default="auto",  # TODO dry
        help="Output format. TODO Fixme. 'auto' chooses 'pyout' if pyout library is installed,"
        " 'summaries' otherwise.",
    )
    parser_ls.add_argument(
        "-F",
        "--fields",
        nargs="+",
        metavar="FIELD",
        help=f"List of fields to show. Prefix is always included implicitly as the first field. "
        f"Available choices: {', '.join(sorted(LS_FIELD_CHOICES))}.",
        choices=LS_FIELD_CHOICES,
        default=[
            "command",
            "exit_code",
            "wall_clock_time",
            "peak_rss",
        ],
    )
    parser_ls.add_argument(
        "--colors",
        action="store_true",
        default=os.getenv("DUCT_COLORS", False),
        help="Use colors in duct output.",
    )
    parser_ls.add_argument(
        "paths",
        nargs="*",
        help="Path to duct report files, only `info.json` would be considered. "
        "If not provided, the program will glob for files that match DUCT_OUTPUT_PREFIX.",
    )
    parser_ls.add_argument(
        "-e",
        "--eval-filter",
        help="Python expression to filter results based on available fields. "
        "The expression is evaluated for each entry, and only those that return True are included. "
        "See --fields for all supported fields. "
        "Example: --eval-filter \"filter_this=='yes'\" filters entries where 'filter_this' is 'yes'. "
        "You can use 're' for regex operations (e.g., --eval-filter \"re.search('2025.02.09.*', prefix)\").",
    )
    parser_ls.set_defaults(func=ls)

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
    else:
        sys.exit(execute(args))
