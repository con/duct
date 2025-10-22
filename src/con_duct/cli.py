import argparse
from dataclasses import dataclass
import logging
import os
import sys
import textwrap
from typing import Any, List, Optional
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

lgr = logging.getLogger("con-duct")
DEFAULT_LOG_LEVEL = os.environ.get("DUCT_LOG_LEVEL", "INFO").upper()

ABOUT_DUCT = """
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
"""


class CustomHelpFormatter(argparse.ArgumentDefaultsHelpFormatter):
    def _fill_text(self, text: str, width: int, _indent: str) -> str:
        return "\n".join([textwrap.fill(line, width) for line in text.splitlines()])


def create_common_parser() -> argparse.ArgumentParser:
    """Create a parser with common arguments shared across all commands."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "-l",
        "--log-level",
        default=DEFAULT_LOG_LEVEL,
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


@dataclass
class RunArguments:
    command: str
    command_args: list[str]
    output_prefix: str
    sample_interval: float
    report_interval: float
    fail_time: float
    clobber: bool
    capture_outputs: Outputs
    outputs: Outputs
    record_types: RecordTypes
    summary_format: str
    colors: bool
    log_level: str
    quiet: bool
    session_mode: SessionMode
    message: str = ""

    def __post_init__(self) -> None:
        if self.report_interval < self.sample_interval:
            raise argparse.ArgumentError(
                None,
                "--report-interval must be greater than or equal to --sample-interval.",
            )

    def execute(self) -> int:
        """Execute the command with these arguments.

        This is a convenience method for tests and library usage.
        """
        return duct_execute(
            command=self.command,
            command_args=self.command_args,
            output_prefix=self.output_prefix,
            sample_interval=self.sample_interval,
            report_interval=self.report_interval,
            fail_time=self.fail_time,
            clobber=self.clobber,
            capture_outputs=self.capture_outputs,
            outputs=self.outputs,
            record_types=self.record_types,
            summary_format=self.summary_format,
            colors=self.colors,
            session_mode=self.session_mode,
            message=self.message,
        )

    @classmethod
    def create_parser(cls) -> argparse.ArgumentParser:
        """Create and configure the argument parser for duct."""
        common_parser = create_common_parser()
        parser = argparse.ArgumentParser(
            allow_abbrev=False,
            description=ABOUT_DUCT,
            formatter_class=CustomHelpFormatter,
            parents=[common_parser],
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

    @classmethod
    def from_argv(
        cls, cli_args: Optional[list[str]] = None, **cli_kwargs: Any
    ) -> "RunArguments":
        parser = cls.create_parser()
        args = parser.parse_args(
            args=cli_args,
            namespace=cli_kwargs and argparse.Namespace(**cli_kwargs) or None,
        )
        return cls(
            command=args.command,
            command_args=args.command_args,
            output_prefix=args.output_prefix,
            sample_interval=args.sample_interval,
            report_interval=args.report_interval,
            fail_time=args.fail_time,
            capture_outputs=args.capture_outputs,
            outputs=args.outputs,
            record_types=args.record_types,
            summary_format=args.summary_format,
            clobber=args.clobber,
            colors=args.colors,
            log_level=args.log_level,
            quiet=args.quiet,
            session_mode=args.mode,
            message=args.message,
        )


def run_command(args: argparse.Namespace) -> int:
    """Execute a command with duct monitoring."""
    return duct_execute(
        command=args.command,
        command_args=args.command_args,
        output_prefix=args.output_prefix,
        sample_interval=args.sample_interval,
        report_interval=args.report_interval,
        fail_time=args.fail_time,
        capture_outputs=args.capture_outputs,
        outputs=args.outputs,
        record_types=args.record_types,
        summary_format=args.summary_format,
        clobber=args.clobber,
        colors=args.colors,
        session_mode=args.mode,
        message=args.message,
    )


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
    parser = argparse.ArgumentParser(
        prog="con-duct",
        description="A suite of commands to manage or manipulate con-duct logs.",
        usage="con-duct <command> [options]",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    common_parser = create_common_parser()
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Subcommand: run
    # Use the parser from RunArguments.create_parser() as a parent
    # to get all the arguments for executing a command with monitoring
    duct_parser = RunArguments.create_parser()
    parser_run = subparsers.add_parser(
        "run",
        help="Execute a command with duct monitoring.",
        description=ABOUT_DUCT,
        parents=[duct_parser],
        add_help=False,  # Parent parser already provides --help
        formatter_class=CustomHelpFormatter,
        allow_abbrev=False,
        prog="con-duct run",
    )
    parser_run.set_defaults(func=run_command)

    # Subcommand: pp
    parser_pp = subparsers.add_parser(
        "pp",
        help="Pretty print a JSON log.",
        parents=[common_parser],
        prog="con-duct pp",
    )
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
        "plot",
        help="Plot resource usage for an execution.",
        parents=[common_parser],
        prog="con-duct plot",
    )
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
    parser_plot.set_defaults(func=matplotlib_plot)

    parser_ls = subparsers.add_parser(
        "ls",
        help="Print execution information for all matching runs.",
        parents=[common_parser],
        prog="con-duct ls",
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
        setup_logging(args)
        sys.exit(execute(args))
