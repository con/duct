import argparse
import logging
import os
import sys
from typing import List, Optional

try:
    from jsonargparse import ArgumentParser
except ImportError:
    print(
        "Error: con-duct requires jsonargparse to be installed.\n"
        "Install it with: pip install con-duct[all]\n"
        "or: pip install jsonargparse[yaml]",
        file=sys.stderr,
    )
    sys.exit(1)

from con_duct import __version__
from con_duct.__main__ import DEFAULT_CONFIG_PATHS, DEFAULT_LOG_LEVEL
from con_duct.suite.ls import LS_FIELD_CHOICES, ls
from con_duct.suite.plot import matplotlib_plot
from con_duct.suite.pprint_json import pprint_json

lgr = logging.getLogger("con-duct")


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
    parser_kwargs = {
        "prog": "con-duct",
        "description": "A suite of commands to manage or manipulate con-duct logs.",
        "usage": "con-duct <command> [options]",
        "default_env": True,
        "env_prefix": "DUCT",
    }

    parser = ArgumentParser(**parser_kwargs)  # type: ignore[arg-type]

    config_paths_env = os.environ.get("DUCT_CONFIG_PATHS")
    if config_paths_env:
        parser.default_config_files = config_paths_env.split(":")
    else:
        parser.default_config_files = DEFAULT_CONFIG_PATHS
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
    subparsers = parser.add_subcommands(
        dest="command", required=False, help="Available subcommands"
    )

    # Subcommand: pp
    parser_pp = ArgumentParser()
    parser_pp.add_argument("file_path", help="JSON file to pretty print.")
    parser_pp.add_argument(
        "-H",
        "--humanize",
        action="store_true",
        help="Convert numeric values to human-readable format",
    )
    subparsers.add_subcommand("pp", parser_pp, help="Pretty print a JSON log.")

    # Subcommand: plot
    parser_plot = ArgumentParser()
    parser_plot.add_argument("file_path", help="duct-produced usage.json file.")
    parser_plot.add_argument(
        "-o",
        "--output",
        help="Output path for the image file. If not specified, plot will be shown and not saved.",
        default=None,
    )
    parser_plot.add_argument(
        "--min-ratio",
        type=float,
        default=3.0,
        help="Minimum ratio for axis unit selection (default: 3.0). Lower values use larger units sooner. "
        "Use -1 to always use base units (seconds, bytes).",
    )
    # parser_plot.add_argument(
    #     "-b",
    #     "--backend",
    #     default=DEFAULT_PLOT_BACKEND,
    #     choices=("matplotlib",)
    #     help="which backend to plot with
    # )
    subparsers.add_subcommand(
        "plot", parser_plot, help="Plot resource usage for an execution."
    )

    # Subcommand: ls
    parser_ls = ArgumentParser()
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
        default=False,
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
    subparsers.add_subcommand(
        "ls", parser_ls, help="Print execution information for all matching runs."
    )

    # Map command names to their handler functions
    command_funcs = {
        "pp": pprint_json,
        "plot": matplotlib_plot,
        "ls": ls,
    }

    # Parse args - use _skip_validation to allow unknown keys in config files
    # This allows sharing config files between duct and con-duct
    args = parser.parse_args(argv, _skip_validation=True)
    args = parser.strip_unknown(args)

    if args.command is None:
        parser.print_help()
    else:
        # Get the subcommand namespace (e.g., args.ls for "ls" command)
        subcommand_args = getattr(args, args.command)
        # Manually set the func based on the command
        subcommand_args.func = command_funcs[args.command]
        # Also preserve log_level from main parser
        subcommand_args.log_level = args.log_level
        sys.exit(execute(subcommand_args))
