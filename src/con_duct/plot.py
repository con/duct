"""Resource-usage plotting for con-duct.

Renders a per-pid pdcpu / pmem cloud overlaid by max (lower bound on
the total) and sum (upper bound on the total) envelopes. The per-pid
overlay is loosely modeled on brainlife's smon task viewer:
https://github.com/brainlife/warehouse/blob/b833b98e3518181eacef71cc04ae773a7592b1a8/ui/src/modals/taskinfo.vue
"""

import argparse
from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from con_duct._utils import etime_to_etimes, is_same_pid, pdcpu_from_pcpu
from con_duct.json_utils import is_info_file, load_info_file, load_usage_file

# Drop pids whose peak pdcpu falls below this threshold AND whose peak rss
# falls below DEFAULT_MIN_PEAK_RSS. A pid notable on either axis is kept.
# Matches brainlife's near-zero filters: 0.5% for pcpu, 10MB for rss.
# rss is still used here as a relevance signal even though the default chart
# does not render an rss line -- a memory-only pid should still contribute
# to the pmem envelope.
DEFAULT_MIN_PEAK_PDCPU = 0.5
DEFAULT_MIN_PEAK_RSS = 10 * 1024 * 1024

# Color per metric (all pid lines for that metric share this color).
PCPU_COLOR = "tab:orange"
PMEM_COLOR = "tab:blue"

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


def _build_pid_series(data: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Walk usage records once, return per-pid time series.

    For each pid present in any record, returns aligned lists of
    ``elapsed`` (seconds since first record), ``pdcpu`` (None where no
    measurement), ``pmem``, ``rss``. ``pdcpu`` is computed from
    consecutive (etime, pcpu) pairs; first observation per pid and any
    record with ``etime == "00:00"`` produce ``pdcpu = None`` and do not
    establish a baseline for the next sample. Filtering is the caller's
    job (see ``_filter_pids``).
    """
    if not data:
        return {}
    base_ts = datetime.fromisoformat(data[0]["timestamp"])
    pid_state: Dict[str, Optional[Tuple[float, float, datetime]]] = {}
    series: Dict[str, Dict[str, Any]] = {}
    for entry in data:
        entry_ts = datetime.fromisoformat(entry["timestamp"])
        elapsed = (entry_ts - base_ts).total_seconds()
        for pid, p in entry.get("processes", {}).items():
            try:
                etime_sec = etime_to_etimes(p.get("etime", ""))
            except ValueError:
                continue
            pcpu = float(p.get("pcpu", 0.0))
            # Use the per-process timestamp (the moment this pid was last
            # sampled) for the wall-delta in is_same_pid -- not the report
            # timestamp. duct emits each report at the end of its interval,
            # but a short-lived pid's last sample within the interval can
            # be many seconds earlier. Comparing Δetime against Δreport
            # timestamp would falsely flag a continuous-but-short pid as
            # reused.
            proc_ts = datetime.fromisoformat(p.get("timestamp", entry["timestamp"]))
            prev = pid_state.get(pid)
            pdcpu: Optional[float] = None
            if etime_sec != 0.0 and prev is not None:
                prev_etime, prev_pcpu, prev_proc_ts = prev
                wall_delta = (proc_ts - prev_proc_ts).total_seconds()
                if is_same_pid(prev_etime, etime_sec, wall_delta):
                    pdcpu = pdcpu_from_pcpu(prev_pcpu, prev_etime, pcpu, etime_sec)
                # else: pid reuse -- pdcpu stays None, re-baseline below.
            entry_series = series.setdefault(
                pid,
                {
                    "cmd": p.get("cmd", ""),
                    "elapsed": [],
                    "pdcpu": [],
                    "pmem": [],
                    "rss": [],
                },
            )
            entry_series["elapsed"].append(elapsed)
            entry_series["pdcpu"].append(pdcpu)
            entry_series["pmem"].append(float(p.get("pmem", 0.0)))
            entry_series["rss"].append(float(p.get("rss", 0.0)))
            # Don't baseline from etime=0 -- next sample is a "first observation".
            pid_state[pid] = None if etime_sec == 0.0 else (etime_sec, pcpu, proc_ts)
    return series


def _peak_pdcpu(s: Dict[str, Any]) -> float:
    measurable = [v for v in s["pdcpu"] if v is not None]
    return max(measurable) if measurable else 0.0


def _peak_rss(s: Dict[str, Any]) -> float:
    return max(s["rss"]) if s["rss"] else 0.0


def _filter_pids(
    series: Dict[str, Dict[str, Any]],
    *,
    min_peak_pdcpu: float = DEFAULT_MIN_PEAK_PDCPU,
    min_peak_rss: float = DEFAULT_MIN_PEAK_RSS,
    drop_ps_observer: bool = False,
) -> Dict[str, Dict[str, Any]]:
    """Trim per-pid series for legibility.

    A pid is kept if it is "notable" on either axis: peak pdcpu reaches
    ``min_peak_pdcpu`` *or* peak rss reaches ``min_peak_rss``. This way an
    idle process holding significant memory still contributes to the pmem
    cloud and envelope, even though the default chart does not render an
    rss line.

    With ``drop_ps_observer``, drops pids whose cmd starts with ``"ps "``.
    """
    out: Dict[str, Dict[str, Any]] = {}
    for pid, s in series.items():
        if drop_ps_observer and s["cmd"].startswith("ps "):
            continue
        if _peak_pdcpu(s) < min_peak_pdcpu and _peak_rss(s) < min_peak_rss:
            continue
        out[pid] = s
    return out


def _envelopes(
    series: Dict[str, Dict[str, Any]],
    metric: str,
) -> Tuple[List[float], List[float], List[float]]:
    """Per-grid-timestamp max and sum across kept pids for ``metric``.

    Each pid contributes a value at every entry-elapsed timestamp where it
    appeared *and* its value at that timestamp is not ``None`` (pdcpu can be
    ``None`` for first-observation, etime=0, sub-quantum, pid-reuse, or the
    negative-pdcpu clamp). Grid points where no kept pid had a value are
    omitted entirely rather than reported as zero -- a missing measurement
    is not the same as zero load.

    The grid is the union of (kept pids') elapsed values; the alternative
    of "every entry timestamp regardless of who appeared" would only add
    grid points that are missing measurements anyway.

    :returns: ``(grid_xs, max_ys, sum_ys)`` aligned, sorted by ``grid_xs``.
    """
    grid: Dict[float, List[float]] = {}
    for s in series.values():
        for x, v in zip(s["elapsed"], s[metric]):
            if v is None:
                continue
            grid.setdefault(x, []).append(v)
    xs = sorted(grid.keys())
    return xs, [max(grid[x]) for x in xs], [sum(grid[x]) for x in xs]


def matplotlib_plot(args: argparse.Namespace) -> int:
    try:
        import matplotlib

        # Use non-interactive backend when saving to file to avoid tkinter issues
        if args.output is not None:
            matplotlib.use("Agg")

        from matplotlib.lines import Line2D
        import matplotlib.pyplot as plt
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
        pid_series = _build_pid_series(data)
    except KeyError as e:
        lgr.error("Usage file %s is missing required field: %s", file_path, e)
        return 1
    except ValueError as e:
        lgr.error("Usage file %s contains invalid data format: %s", file_path, e)
        return 1
    except Exception as e:
        lgr.error("Error processing usage file %s: %s", file_path, e)
        return 1

    filtered = _filter_pids(pid_series, min_peak_pdcpu=DEFAULT_MIN_PEAK_PDCPU)

    fig, ax = plt.subplots()

    # Per-pid traces: dotted, faint, single color per metric. The cloud of
    # pid lines reads as background texture; the envelopes carry the signal.
    for s in filtered.values():
        pdcpu_xs = [t for t, v in zip(s["elapsed"], s["pdcpu"]) if v is not None]
        pdcpu_ys = [v for v in s["pdcpu"] if v is not None]
        if pdcpu_xs:
            ax.plot(  # type: ignore[call-arg]
                pdcpu_xs,
                pdcpu_ys,
                color=PCPU_COLOR,
                linestyle=":",
                linewidth=0.8,
                alpha=0.4,
            )
        ax.plot(  # type: ignore[call-arg]
            s["elapsed"],
            s["pmem"],
            color=PMEM_COLOR,
            linestyle=":",
            linewidth=0.8,
            alpha=0.4,
        )

    # Envelopes: max (lower bound on total) solid, sum (upper bound) dashed.
    # If some pid was at 50%, the total was at least 50% -- max is a true
    # lower bound. The sum is an upper bound that can blow past 100% on
    # multi-core (per-pid pdcpu doesn't know about cores) and overstate
    # memory (shared pages get counted multiple times in pmem); both
    # caveats are accepted -- the goal is "more meaningful than now".
    for metric, color in (("pdcpu", PCPU_COLOR), ("pmem", PMEM_COLOR)):
        env_xs, max_ys, sum_ys = _envelopes(filtered, metric)
        if not env_xs:
            continue
        ax.plot(  # type: ignore[call-arg]
            env_xs, max_ys, color=color, linestyle="-", linewidth=2.0
        )
        ax.plot(  # type: ignore[call-arg]
            env_xs, sum_ys, color=color, linestyle="--", linewidth=1.5
        )

    ax.set_xlabel("Elapsed Time")
    ax.set_ylabel("pcpu / pmem (%)")
    if filtered:
        # Two legends, color-agnostic linestyle key on the right and metric
        # color key on the left. Linestyle entries are listed in the order
        # a viewer's eye scans the chart: upper bound (the high dashed line),
        # lower bound (the solid line below it), per-pid (dotted cloud).
        style_handles = [
            Line2D(
                [0],
                [0],
                color="black",
                linestyle="--",
                linewidth=1.5,
                label="upper bound",
            ),
            Line2D(
                [0],
                [0],
                color="black",
                linestyle="-",
                linewidth=2.0,
                label="lower bound",
            ),
            Line2D(
                [0], [0], color="black", linestyle=":", linewidth=0.8, label="per-pid"
            ),
        ]
        style_legend = ax.legend(  # type: ignore[call-arg]
            handles=style_handles, loc="upper right", fontsize=9
        )
        ax.add_artist(style_legend)  # type: ignore[attr-defined]
        color_handles = [
            Line2D([0], [0], color=PCPU_COLOR, linewidth=2.0, label="pcpu"),
            Line2D([0], [0], color=PMEM_COLOR, linewidth=2.0, label="pmem"),
        ]
        ax.legend(handles=color_handles, loc="upper left", fontsize=9)  # type: ignore[call-arg]

    ax.xaxis.set_major_formatter(  # type: ignore[attr-defined]
        HumanizedAxisFormatter(min_ratio=args.min_ratio, units=_TIME_UNITS)
    )

    plt.title("Resource Usage Over Time (per pid)")

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
