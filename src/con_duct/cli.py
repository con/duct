import argparse
import logging
import os
from pathlib import Path
import re
import sys
import textwrap
from typing import List, Optional
from con_duct import __version__
from con_duct.duct_main import (
    DUCT_OUTPUT_PREFIX,
    EXECUTION_SUMMARY_FORMAT,
    Outputs,
    RecordTypes,
    SessionMode,
)
from con_duct.duct_main import execute as duct_execute
from con_duct.ls import LS_FIELD_CHOICES, ls
from con_duct.plot import matplotlib_plot
from con_duct.pprint_json import pprint_json

# Default .env file search paths (in precedence order)
DEFAULT_CONFIG_PATHS_LIST = (
    "/etc/duct/.env",
    "${XDG_CONFIG_HOME:-~/.config}/duct/.env",
    ".duct/.env",
)
DEFAULT_CONFIG_PATHS = os.pathsep.join(DEFAULT_CONFIG_PATHS_LIST)


def load_duct_env_files() -> List[tuple[str, str]]:
    """Load environment variables from .env files in multiple locations.

    Searches for .env files specified in DUCT_CONFIG_PATHS (or DEFAULT_CONFIG_PATHS).
    Files are loaded in reverse order so later files override earlier ones.

    Environment variables already set in the environment will NOT be overridden
    by values from .env files, maintaining proper precedence:
    CLI args > explicit env vars > .env files > hardcoded defaults

    Gracefully handles missing python-dotenv package or missing .env files.

    Returns:
        List of (level_name, message) tuples for deferred logging.
    """
    log_buffer: List[tuple[str, str]] = []

    try:
        from dotenv import load_dotenv
    except ImportError:
        # python-dotenv not installed, skip .env file loading
        log_buffer.append(
            ("INFO", "python-dotenv not installed, skipping .env file loading")
        )
        return log_buffer

    config_paths_str = os.getenv("DUCT_CONFIG_PATHS", DEFAULT_CONFIG_PATHS)
    log_buffer.append(("DEBUG", f"Searching for .env files in: {config_paths_str}"))

    # Expand ${VAR:-default} syntax in the paths string ie ${XDG_CONFIG_HOME:-~/.config}
    def expand_var(match: re.Match) -> str:
        var_expr = match.group(1)
        if ":-" in var_expr:
            var_name, default = var_expr.split(":-", 1)
            return os.getenv(var_name, default)
        return os.getenv(var_expr, "")

    config_paths_str = re.sub(r"\$\{([^}]+)\}", expand_var, config_paths_str)
    search_paths = [
        val for p in config_paths_str.split(os.pathsep) if (val := p.strip())
    ]

    # Load in reverse order so later paths override earlier ones (once set, vars are skipped)
    loaded_count = 0
    for path in reversed(search_paths):
        expanded_path = Path(path).expanduser()
        if expanded_path.exists():
            log_buffer.append(("INFO", f"Loading .env file: {expanded_path}"))
            try:
                load_dotenv(expanded_path, override=False)
                loaded_count += 1
            except PermissionError as e:
                log_buffer.append(
                    ("WARNING", f"Cannot read .env file {expanded_path}: {e}")
                )
            except ValueError as e:
                log_buffer.append(
                    ("WARNING", f"Skipping malformed .env file {expanded_path}: {e}")
                )
        else:
            log_buffer.append(
                ("DEBUG", f".env file not found (skipping): {expanded_path}")
            )

    if loaded_count == 0:
        log_buffer.append(("INFO", "No .env files found"))

    return log_buffer


def _replay_early_logs(log_buffer: List[tuple[str, str]]) -> None:
    """Replay buffered log messages through the configured logger.

    Should be called after setup_logging() to ensure buffered messages from
    .env file loading are properly logged with the user's chosen log level.

    Args:
        log_buffer: List of (level_name, message) tuples to replay.
    """
    for level_name, message in log_buffer:
        lgr.log(getattr(logging, level_name), message)


lgr = logging.getLogger("con-duct")

# Format default config paths as a bulleted list for help text
_config_paths_list = "\n".join(f"    - {path}" for path in DEFAULT_CONFIG_PATHS_LIST)

ABOUT_DUCT = f"""
duct is a lightweight wrapper that collects execution data for an arbitrary
command. This command can be invoked as either 'duct' or 'con-duct run'.

Execution data includes execution time, system information, and resource usage
statistics of the command and all its child processes. It is intended to
simplify the problem of recording the resources necessary to execute a command,
particularly in an HPC environment.

Resource usage is determined by polling (at a sample-interval).
During execution, duct produces a JSON lines (see https://jsonlines.org) file
with one data point recorded for each report (at a report-interval).

limitations:
  Duct uses session id to track the command process and its children, so it
  cannot handle the situation where a process creates a new session.
  If a command spawns child processes, duct will collect data on them, but
  duct exits as soon as the primary process exits.

environment variables:
  Many duct options can be configured by environment variables (which are
  overridden by command line options).

  DUCT_LOG_LEVEL: see --log-level
  DUCT_OUTPUT_PREFIX: see --output-prefix
  DUCT_SUMMARY_FORMAT: see --summary-format
  DUCT_SAMPLE_INTERVAL: see --sample-interval
  DUCT_REPORT_INTERVAL: see --report-interval
  DUCT_CAPTURE_OUTPUTS: see --capture-outputs
  DUCT_MESSAGE: see --message
  DUCT_CONFIG_PATHS: paths to .env files separated by platform path separator
    (':' on Unix) (see below)

.env files:
  Environment variables can also be set via .env files. By default, duct
  searches the following locations (later files override earlier ones):

{_config_paths_list}

  Override the search paths by setting DUCT_CONFIG_PATHS with paths separated
  by the platform path separator (':' on Unix)
  (e.g., export DUCT_CONFIG_PATHS="/custom/path.env:~/.myduct.env").

  Example .env file content:
    # Set default log level
    DUCT_LOG_LEVEL=DEBUG

    # Configure intervals
    DUCT_SAMPLE_INTERVAL=2.0
    DUCT_REPORT_INTERVAL=120.0

    # Set default output location
    DUCT_OUTPUT_PREFIX=~/duct-logs/{{datetime_filesafe}}-{{pid}}_

    # Add execution notes (multiline)
    DUCT_MESSAGE="Experiment run for paper revision
    Using updated dataset from 2025-10-30
    See lab notebook page 42 for details"

  Supported .env syntax (via python-dotenv):
    - KEY=value (basic assignment)
    - KEY="value with spaces" (quoted values)
    - KEY='single quotes' (single-quoted values)
    - # comments (hash comments)
    - Empty lines (ignored)
    - Multiline values (use quotes)

  Precedence (highest to lowest):
    1. Command line arguments
    2. Explicit environment variables
    3. .env file values (later paths override earlier paths)
    4. Hardcoded defaults

  Notes:
    - .env file support requires python-dotenv (pip install con-duct[all])
    - DUCT_CONFIG_PATHS cannot be set in .env files (must be set before loading)
    - Malformed, unreadable, or missing .env files are skipped and logged
"""


class CustomHelpFormatter(argparse.ArgumentDefaultsHelpFormatter):
    """Override allows helptext to respect newlines in ABOUT_DUCT"""

    def _fill_text(self, text: str, width: int, _indent: str) -> str:
        return "\n".join([textwrap.fill(line, width) for line in text.splitlines()])


def _create_common_parser() -> argparse.ArgumentParser:
    """Create a parser with common arguments shared across all commands."""
    parser = argparse.ArgumentParser(add_help=False)  # help provided by child
    parser.add_argument(
        "-l",
        "--log-level",
        default=os.getenv("DUCT_LOG_LEVEL", "INFO").upper(),
        choices=("NONE", "CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"),
        type=str.upper,
        help="Level of log output to stderr, use NONE to entirely disable.",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="[deprecated, use log level NONE] Disable duct logging output (to stderr)",
    )
    return parser


def setup_logging(args: argparse.Namespace) -> None:
    """Configure logging based on parsed arguments.

    Handles both --log-level and --quiet flags, applying them consistently
    across all subcommands.
    """
    log_level = args.log_level

    # Handle deprecated --quiet flag
    if args.quiet:
        log_level = "NONE"

    # Special case: NONE means disable all logging
    if log_level == "NONE":
        logging.disable(logging.CRITICAL)
    else:
        logging.basicConfig(
            format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
            level=log_level,
        )


def _create_run_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser for the 'run' command."""
    parser = argparse.ArgumentParser(
        allow_abbrev=False,
        description=ABOUT_DUCT,
        formatter_class=CustomHelpFormatter,
        add_help=False,  # help provided by child
    )
    parser.add_argument(
        "command",
        metavar="command [command_args ...]",
        help="The command to execute, along with its arguments.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "command_args", nargs=argparse.REMAINDER, help="Arguments for the command."
    )
    parser.add_argument(
        "-p",
        "--output-prefix",
        type=str,
        default=DUCT_OUTPUT_PREFIX,
        help="File string format to be used as a prefix for the files -- the captured "
        "stdout and stderr and the resource usage logs. The understood variables are "
        "{datetime}, {datetime_filesafe}, and {pid}. "
        "Leading directories will be created if they do not exist. "
        "You can also provide value via DUCT_OUTPUT_PREFIX env variable. ",
    )
    parser.add_argument(
        "--summary-format",
        type=str,
        default=os.getenv("DUCT_SUMMARY_FORMAT", EXECUTION_SUMMARY_FORMAT),
        help="Output template to use when printing the summary following execution. "
        "Accepts custom conversion flags: "
        "!S: Converts filesizes to human readable units, green if measured, red if None. "
        "!E: Colors exit code, green if falsey, red if truthy, and red if None. "
        "!X: Colors green if truthy, red if falsey. "
        "!N: Colors green if not None, red if None",
    )
    parser.add_argument(
        "--colors",
        action="store_true",
        default=os.getenv("DUCT_COLORS", False),
        help="Use colors in duct output.",
    )
    parser.add_argument(
        "--clobber",
        action="store_true",
        help="Replace log files if they already exist.",
    )
    parser.add_argument(
        "--sample-interval",
        "--s-i",
        type=float,
        default=float(os.getenv("DUCT_SAMPLE_INTERVAL", "1.0")),
        help="Interval in seconds between status checks of the running process. "
        "Sample interval must be less than or equal to report interval, and it achieves the "
        "best results when sample is significantly less than the runtime of the process.",
    )
    parser.add_argument(
        "--report-interval",
        "--r-i",
        type=float,
        default=float(os.getenv("DUCT_REPORT_INTERVAL", "60.0")),
        help="Interval in seconds at which to report aggregated data.",
    )
    parser.add_argument(
        "--fail-time",
        "--f-t",
        type=float,
        default=float(os.getenv("DUCT_FAIL_TIME", "3.0")),
        help="If command fails in less than this specified time (seconds), duct would remove logs. "
        "Set to 0 if you would like to keep logs for a failing command regardless of its run time. "
        "Set to negative (e.g. -1) if you would like to not keep logs for any failing command.",
    )

    parser.add_argument(
        "-c",
        "--capture-outputs",
        default=os.getenv("DUCT_CAPTURE_OUTPUTS", "all"),
        choices=list(Outputs),
        type=Outputs,
        help="Record stdout, stderr, all, or none to log files. "
        "You can also provide value via DUCT_CAPTURE_OUTPUTS env variable.",
    )
    parser.add_argument(
        "-o",
        "--outputs",
        default="all",
        choices=list(Outputs),
        type=Outputs,
        help="Print stdout, stderr, all, or none to stdout/stderr respectively.",
    )
    parser.add_argument(
        "-t",
        "--record-types",
        default="all",
        choices=list(RecordTypes),
        type=RecordTypes,
        help="Record system-summary, processes-samples, or all",
    )
    parser.add_argument(
        "-m",
        "--message",
        type=str,
        default=os.getenv("DUCT_MESSAGE", ""),
        help="Record a descriptive message about the purpose of this execution. "
        "You can also provide value via DUCT_MESSAGE env variable.",
    )
    parser.add_argument(
        "--mode",
        default="new-session",
        choices=list(SessionMode),
        type=SessionMode,
        help="Session mode: 'new-session' creates a new session for the command (default), "
        "'current-session' tracks the current session instead of starting a new one. "
        "Useful for tracking slurm jobs or other commands that should run in the current session.",
    )
    return parser


def _create_pp_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser for the 'pp' command."""
    parser = argparse.ArgumentParser(
        add_help=False,  # help provided by child
    )
    parser.add_argument("file_path", help="JSON file to pretty print.")
    parser.add_argument(
        "-H",
        "--humanize",
        action="store_true",
        help="Convert numeric values to human-readable format",
    )
    return parser


def _create_plot_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser for the 'plot' command."""
    parser = argparse.ArgumentParser(
        add_help=False,  # help provided by child
    )
    parser.add_argument("file_path", help="duct-produced usage file.")
    parser.add_argument(
        "-o",
        "--output",
        help="Output path for the image file. If not specified, plot will be shown "
        "interactively (requires a display). Use this option in headless/server environments.",
        default=None,
    )
    parser.add_argument(
        "--min-ratio",
        type=float,
        default=3.0,
        help="Minimum ratio for axis unit selection (default: 3.0). Lower values use larger units sooner. "
        "Use -1 to always use base units (seconds, bytes).",
    )
    return parser


def _create_ls_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser for the 'ls' command."""
    parser = argparse.ArgumentParser(
        add_help=False,  # help provided by child
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=("auto", "pyout", "summaries", "json", "json_pp", "yaml"),
        default="auto",
        help="Output format. TODO Fixme. 'auto' chooses 'pyout' if pyout library is installed,"
        " 'summaries' otherwise.",
    )
    parser.add_argument(
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
    parser.add_argument(
        "--colors",
        action="store_true",
        default=os.getenv("DUCT_COLORS", False),
        help="Use colors in duct output.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Path to duct report files, only `info.json` would be considered. "
        "If not provided, the program will glob for files that match DUCT_OUTPUT_PREFIX.",
    )
    parser.add_argument(
        "-e",
        "--eval-filter",
        help="Python expression to filter results based on available fields. "
        "The expression is evaluated for each entry, and only those that return True are included. "
        "See --fields for all supported fields. "
        "Example: --eval-filter \"filter_this=='yes'\" filters entries where 'filter_this' is 'yes'. "
        "You can use 're' for regex operations (e.g., --eval-filter \"re.search('2025.02.09.*', prefix)\").",
    )
    parser.add_argument(
        "--reverse",
        action="store_true",
        help="List entries in reverse order (most recent first).",
    )
    return parser


def run_command(args: argparse.Namespace) -> int:
    """Execute a command with duct monitoring."""
    kwargs = vars(args).copy()
    # Remove arguments that are not for duct_execute
    for key in ("func", "log_level", "quiet"):
        kwargs.pop(key, None)
    return duct_execute(**kwargs)


def execute(args: argparse.Namespace) -> int:
    """Execute the subcommand function and return its exit code."""
    result = args.func(args)
    if not isinstance(result, int):
        raise TypeError(
            f"Each con-duct subcommand must return an int returncode, got {type(result)}"
        )
    return result


def duct_entrypoint() -> None:
    """Entry point for the 'duct' command - delegates to 'con-duct run'."""
    os.execvp("con-duct", ["con-duct", "run"] + sys.argv[1:])


def main(argv: Optional[List[str]] = None) -> None:
    # Load .env files before parser creation so defaults pick up env vars
    env_log_buffer = load_duct_env_files()

    parser = argparse.ArgumentParser(
        prog="con-duct",
        description="A suite of commands to manage or manipulate con-duct logs.",
        usage="con-duct <command> [options]",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    common_parser = _create_common_parser()
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Subcommand: run
    parser_run = subparsers.add_parser(
        "run",
        help="Execute a command with duct monitoring.",
        description=ABOUT_DUCT,
        parents=[common_parser, _create_run_parser()],
        formatter_class=CustomHelpFormatter,
        allow_abbrev=False,
        prog="con-duct run",
    )
    parser_run.set_defaults(func=run_command)

    # Subcommand: pp
    parser_pp = subparsers.add_parser(
        "pp",
        help="Pretty print a JSON log.",
        parents=[common_parser, _create_pp_parser()],
        prog="con-duct pp",
    )
    parser_pp.set_defaults(func=pprint_json)

    # Subcommand: plot
    parser_plot = subparsers.add_parser(
        "plot",
        help="Plot resource usage for an execution.",
        parents=[common_parser, _create_plot_parser()],
        prog="con-duct plot",
    )
    parser_plot.set_defaults(func=matplotlib_plot)

    parser_ls = subparsers.add_parser(
        "ls",
        help="Print execution information for all matching runs.",
        parents=[common_parser, _create_ls_parser()],
        prog="con-duct ls",
    )
    parser_ls.set_defaults(func=ls)

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return

    setup_logging(args)
    _replay_early_logs(env_log_buffer)
    sys.exit(execute(args))
