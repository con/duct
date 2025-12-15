import argparse
from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any, List, Optional, Tuple
from con_duct.json_utils import is_info_file, load_info_file, load_usage_file

lgr = logging.getLogger(__name__)

_TIME_UNITS = [
    ("s", 1),
    ("min", 60),
    ("h", 3600),
    ("d", 86400),
]

_MEMORY_UNITS = [
    ("B", 1),
    ("KB", 1024**1),
    ("MB", 1024**2),
    ("GB", 1024**3),
    ("TB", 1024**4),
    ("PB", 1024**5),
]


# Class in a Class to avoid importing matplotlib until we need it.
class HumanizedAxisFormatter:
    """Format units for human-readable plot axes."""

    def __new__(cls, min_ratio: float, units: list) -> Any:  # noqa: U100
        from matplotlib.ticker import Formatter

        class _HumanizedAxisFormatter(Formatter):
            def __init__(self, min_ratio: float, units: list):
                super().__init__()
                self.min_ratio = min_ratio
                self.units: List[Tuple[str, int]] = units

            def pick_unit(self, base_value: float) -> Tuple[str, int]:
                # If min_ratio is -1, always use base unit
                if self.min_ratio == -1:
                    return self.units[0]

                unit: Tuple[str, int] = self.units[0]
                for name, divisor in self.units:
                    if base_value / divisor >= self.min_ratio:
                        unit = (name, divisor)
                return unit

            def __call__(self, x: float, _pos: Optional[int] = 0) -> str:
                """Called by matplotlib to value for axis tick.
                Args:
                    x: value in base unit

                Returns:
                    Formatted human readable unit string
                """
                xmin, xmax = self.axis.get_view_interval()  # type: ignore[union-attr]
                span_sec = abs(xmax - xmin) or 1.0
                name, divisor = self.pick_unit(span_sec)
                value = x / divisor
                return f"{value:.1f}{name}"

        return _HumanizedAxisFormatter(min_ratio=min_ratio, units=units)


def matplotlib_plot(args: argparse.Namespace) -> int:
    try:
        import matplotlib

        # Use non-interactive backend when saving to file to avoid tkinter issues
        if args.output is not None:
            matplotlib.use("Agg")

        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError as e:
        lgr.error("con-duct plot failed: missing dependency: %s", e)
        return 1
    except AttributeError as e:
        lgr.error(
            "con-duct plot failed to initialize display backend: %s. "
            "Try using --output to save the plot to a file instead.",
            e,
        )
        return 1

    # Try to import backend registry (added in 3.9)
    try:
        from matplotlib.backends import backend_registry  # type: ignore[attr-defined]
        from matplotlib.backends.registry import BackendFilter
    except (ImportError, AttributeError):
        backend_registry = None  # type: ignore[assignment]
        BackendFilter = None  # type: ignore[assignment,misc]
        # Warn early if we won't be able to verify backend compatibility
        if args.output is None:
            lgr.warning(
                "Using matplotlib < 3.9 which lacks backend registry. "
                "Cannot verify if your backend supports interactive display. "
                "If plotting fails, use --output to save to a file instead."
            )

    # Handle info.json files by determining the path to usage file
    file_path = Path(args.file_path)
    if is_info_file(str(file_path)):
        try:
            info_data = load_info_file(str(file_path))
            rel_usage_path = Path(info_data["output_paths"]["usage"])
            file_path = file_path.with_name(rel_usage_path.name)
        except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
            lgr.error("Error reading info file %s: %s", args.file_path, e)
            return 1

    try:
        data = load_usage_file(str(file_path))
    except FileNotFoundError:
        lgr.error("File %s was not found.", file_path)
        return 1
    except json.JSONDecodeError:
        lgr.error("File %s contained invalid JSON.", file_path)
        return 1

    try:
        # Convert timestamps to datetime objects
        timestamps = [datetime.fromisoformat(entry["timestamp"]) for entry in data]

        # Calculate elapsed time in seconds
        elapsed_time = np.array(
            [(ts - timestamps[0]).total_seconds() for ts in timestamps]
        )

        # Extract other data
        pmem = np.array([entry["totals"]["pmem"] for entry in data])
        pcpu = np.array([entry["totals"]["pcpu"] for entry in data])
        rss_kb = np.array([entry["totals"]["rss"] for entry in data])
        vsz_kb = np.array([entry["totals"]["vsz"] for entry in data])
    except KeyError as e:
        lgr.error("Usage file %s is missing required field: %s", file_path, e)
        return 1
    except ValueError as e:
        lgr.error("Usage file %s contains invalid data format: %s", file_path, e)
        return 1
    except Exception as e:
        lgr.error("Error processing usage file %s: %s", file_path, e)
        return 1

    # Plotting
    fig, ax1 = plt.subplots()

    # Plot pmem and pcpu on primary y-axis
    ax1.plot(elapsed_time, pmem, label="pmem (%)", color="tab:blue")
    ax1.plot(elapsed_time, pcpu, label="pcpu (%)", color="tab:orange")
    ax1.set_xlabel("Elapsed Time")
    ax1.set_ylabel("Percentage")
    ax1.legend(loc="upper left")

    ax1.xaxis.set_major_formatter(  # type: ignore[attr-defined]
        HumanizedAxisFormatter(min_ratio=args.min_ratio, units=_TIME_UNITS)
    )

    # Create a second y-axis for rss and vsz
    ax2 = ax1.twinx()  # type: ignore[attr-defined]
    ax2.plot(elapsed_time, rss_kb, label="rss", color="tab:green")
    ax2.plot(elapsed_time, vsz_kb, label="vsz", color="tab:red")
    ax2.set_ylabel("Memory")
    ax2.legend(loc="upper right")

    ax2.yaxis.set_major_formatter(  # type: ignore[attr-defined]
        HumanizedAxisFormatter(min_ratio=args.min_ratio, units=_MEMORY_UNITS)
    )

    plt.title("Resource Usage Over Time")

    # Adjust layout to prevent labels from being cut off
    plt.tight_layout()  # type: ignore[attr-defined]

    if args.output is not None:
        plt.savefig(args.output)
        lgr.info(
            "Successfully rendered input file: %s to output %s", file_path, args.output
        )
    else:
        # Check if the current backend can display plots interactively
        if backend_registry is not None:
            # matplotlib >= 3.9: Use backend registry to check if backend is interactive
            try:
                # get_backend() added in 3.10
                current_backend = matplotlib.get_backend()  # type: ignore[attr-defined]
            except AttributeError:
                # matplotlib 3.9.x: use rcParams instead
                current_backend = matplotlib.rcParams["backend"]  # type: ignore[attr-defined]
            interactive_backends = backend_registry.list_builtin(
                BackendFilter.INTERACTIVE
            )

            if current_backend in interactive_backends:
                plt.show()
            else:
                lgr.error(
                    "Cannot display plot: your current matplotlib backend is %s "
                    "which is a not a known interactive backend.",
                    current_backend,
                )
                lgr.error(
                    "Either set environment variable MPLBACKEND to an interactive backend or "
                    "use --output to save the plot to a file instead."
                )
                lgr.error(
                    "For more info: https://matplotlib.org/stable/users/explain/figure/backends.html"
                )
                return 1
        else:
            # matplotlib < 3.9: Cannot check backend interactivity, just try plt.show()
            # mypy thinks this is unreachable but import fails on old matplotlib
            plt.show()  # type: ignore[unreachable]

    return 0
