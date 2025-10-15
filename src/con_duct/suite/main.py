import argparse
import logging
import os
import sys
from typing import List, Optional
from jsonargparse import ArgumentParser
from con_duct import __version__
from con_duct.__main__ import (
    DEFAULT_CONFIG_PATHS,
    DEFAULT_LOG_LEVEL,
    DEFAULT_OUTPUT_PREFIX,
    DuctHelpFormatter,
)
from con_duct.suite.ls import LS_FIELD_CHOICES, ls
from con_duct.suite.plot import matplotlib_plot
from con_duct.suite.pprint_json import pprint_json

lgr = logging.getLogger("con-duct")


class ConDuctHelpFormatter(DuctHelpFormatter):  # type: ignore[misc]
    """Custom formatter that suppresses config validation errors in help output.

    When con-duct shares config files with duct, validation errors may appear
    in help output for duct-specific keys. This formatter filters them out.
    Also suppresses environment variable display for subcommands.
    """

    def format_help(self) -> str:
        import re

        help_text = super().format_help()
        # Remove the validation error message using regex
        # Pattern matches from ", Note: tried getting defaults..." to "...is not expected"
        pattern = r",\s*Note:\s*tried getting defaults.*?is not\s+expected"
        help_text = re.sub(pattern, "", help_text, flags=re.DOTALL)

        # Remove all ENV: lines from the subcommands section
        # See https://github.com/omni-us/jsonargparse/issues/786 for feature request
        # to suppress env vars per-argument instead of needing this workaround
        # Split by "subcommands:" header, then remove ENV: lines from everything after
        parts = help_text.split("subcommands:", 1)
        if len(parts) == 2:
            before, after = parts
            # Remove all ENV: lines from the subcommands section
            after = re.sub(r"^\s*ENV:\s+\S+\s*$", "", after, flags=re.MULTILINE)
            help_text = before + "subcommands:" + after

        return help_text


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
        "formatter_class": ConDuctHelpFormatter,
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
    parser.add_argument(
        "-p",
        "--output-prefix",
        type=str,
        default=DEFAULT_OUTPUT_PREFIX,
        help="File prefix pattern used by duct. Shared with duct's "
        "--output-prefix for config/env compatibility.",
    )
    subparsers = parser.add_subcommands(
        dest="command", required=False, help="Available subcommands"
    )

    # Subcommand: pp
    parser_pp = ArgumentParser(formatter_class=ConDuctHelpFormatter)
    parser_pp.add_argument("file_path", help="JSON file to pretty print.")
    parser_pp.add_argument(
        "-H",
        "--humanize",
        action="store_true",
        help="Convert numeric values to human-readable format",
    )
    subparsers.add_subcommand("pp", parser_pp, help="Pretty print a JSON log.")

    # Subcommand: plot
    parser_plot = ArgumentParser(formatter_class=ConDuctHelpFormatter)
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
    parser_ls = ArgumentParser(formatter_class=ConDuctHelpFormatter)
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
        "If not provided, searches using the output-prefix pattern "
        "(from --output-prefix, DUCT_OUTPUT_PREFIX env, or config).",
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
        # Also preserve log_level and output_prefix from main parser
        subcommand_args.log_level = args.log_level
        if hasattr(args, "output_prefix"):
            subcommand_args.output_prefix = args.output_prefix
        sys.exit(execute(subcommand_args))
