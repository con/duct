"""Resource-usage plotting for con-duct.

Renders a per-pid pdcpu / rss cloud overlaid by max (lower bound on
the total) and sum (upper bound on the total) envelopes. pcpu lives
on the primary y-axis (percent), rss on a secondary y-axis (bytes).
The per-pid overlay is loosely modeled on brainlife's smon task viewer:
https://github.com/brainlife/warehouse/blob/b833b98e3518181eacef71cc04ae773a7592b1a8/ui/src/modals/taskinfo.vue
"""

import argparse
from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from con_duct._constants import SUFFIXES
from con_duct._formatter import FILESIZE_UNITS, SummaryFormatter
from con_duct._utils import etime_to_etimes, is_same_pid, pdcpu_from_pcpu
from con_duct.json_utils import is_info_file, load_info_file, load_usage_file

# Color per metric (all pid lines for that metric share this color).
PCPU_COLOR = "tab:orange"
RSS_COLOR = "tab:blue"

# --cpu choices.
# ps-pcpu: raw lifetime ratio from `ps -o pcpu`, no transformation.
# ps-cpu-timepoint: delta-corrected pdcpu computed from consecutive
# (pcpu, etime) pairs -- our derived time-point estimate.
CPU_MODE_PS_PCPU = "ps-pcpu"
CPU_MODE_PS_CPU_TIMEPOINT = "ps-cpu-timepoint"
CPU_MODES = (CPU_MODE_PS_PCPU, CPU_MODE_PS_CPU_TIMEPOINT)

lgr = logging.getLogger(__name__)

_TIME_UNITS = [
    ("s", 1),
    ("min", 60),
    ("h", 3600),
    ("d", 86400),
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


def _build_pid_series(
    data: List[Dict[str, Any]],
    cpu_mode: str = CPU_MODE_PS_PCPU,
) -> Dict[str, Dict[str, Any]]:
    """Walk usage records once, return per-pid time series.

    For each pid present in any record, returns aligned lists of
    ``elapsed`` (seconds since first record), ``cpu``, ``pmem``,
    ``rss``.

    The ``cpu`` field is populated according to ``cpu_mode``:

    - ``ps-pcpu``: raw ``pcpu`` from each record, untransformed. Every
      record contributes a value; no entry is dropped.
    - ``ps-cpu-timepoint``: delta-corrected pdcpu computed from
      consecutive (etime, pcpu) pairs. ``None`` for first observation
      per pid, records with ``etime == "00:00"``, sub-quantum
      intervals, pid reuse, and the negative-pdcpu clamp.
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
            pcpu = float(p.get("pcpu", 0.0))
            cpu_value: Optional[float]
            if cpu_mode == CPU_MODE_PS_PCPU:
                cpu_value = pcpu
            else:
                try:
                    etime_sec = etime_to_etimes(p.get("etime", ""))
                except ValueError:
                    continue
                # Use the per-process timestamp (the moment this pid was last
                # sampled) for the wall-delta in is_same_pid -- not the report
                # timestamp. duct emits each report at the end of its interval,
                # but a short-lived pid's last sample within the interval can
                # be many seconds earlier. Comparing Δetime against Δreport
                # timestamp would falsely flag a continuous-but-short pid as
                # reused.
                proc_ts = datetime.fromisoformat(p.get("timestamp", entry["timestamp"]))
                prev = pid_state.get(pid)
                cpu_value = None
                if etime_sec != 0.0 and prev is not None:
                    prev_etime, prev_pcpu, prev_proc_ts = prev
                    wall_delta = (proc_ts - prev_proc_ts).total_seconds()
                    if is_same_pid(prev_etime, etime_sec, wall_delta):
                        cpu_value = pdcpu_from_pcpu(
                            prev_pcpu, prev_etime, pcpu, etime_sec
                        )
                    # else: pid reuse -- cpu stays None, re-baseline below.
                # Don't baseline from etime=0 -- next sample is a "first observation".
                pid_state[pid] = (
                    None if etime_sec == 0.0 else (etime_sec, pcpu, proc_ts)
                )
            entry_series = series.setdefault(
                pid,
                {
                    "cmd": p.get("cmd", ""),
                    "elapsed": [],
                    "cpu": [],
                    "pmem": [],
                    "rss": [],
                },
            )
            entry_series["elapsed"].append(elapsed)
            entry_series["cpu"].append(cpu_value)
            entry_series["pmem"].append(float(p.get("pmem", 0.0)))
            entry_series["rss"].append(float(p.get("rss", 0.0)))
    return series


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


def _totals_rss_series(data: List[Dict[str, Any]]) -> Tuple[List[float], List[float]]:
    """Return ``(elapsed, totals.rss)`` per record.

    ``totals.rss`` is duct's max-of-(sum-per-sample) within each report
    interval -- the highest concurrent rss observed at any single sample
    in that interval. Used as the rss upper-bound line on the chart,
    replacing sum-of-per-pid-peaks (which over-counts pids whose peaks
    never coexisted within the same sample -- "phantom coexistence").
    """
    if not data:
        return [], []
    base = datetime.fromisoformat(data[0]["timestamp"])
    xs: List[float] = []
    ys: List[float] = []
    for entry in data:
        xs.append((datetime.fromisoformat(entry["timestamp"]) - base).total_seconds())
        ys.append(float(entry["totals"]["rss"]))
    return xs, ys


def _load_host_memory_total(file_path: Path) -> Optional[int]:
    """Best-effort lookup of ``system.memory_total`` (bytes) from info.json.

    Accepts either an info.json path or a usage path; for the latter, falls
    back to a sibling info.json named by stripping the usage suffix and
    appending ``info.json``. Returns ``None`` on any failure -- the caller
    treats absence as "host RAM unknown" and renders a plain legend label.
    """
    try:
        if is_info_file(str(file_path)):
            info_data = load_info_file(str(file_path))
        else:
            usage_str = str(file_path)
            sibling: Optional[Path] = None
            for suffix in (SUFFIXES["usage"], SUFFIXES["usage_legacy"]):
                if usage_str.endswith(suffix):
                    sibling = Path(usage_str[: -len(suffix)] + SUFFIXES["info"])
                    break
            if sibling is None or not sibling.exists():
                return None
            info_data = load_info_file(str(sibling))
        value = info_data["system"]["memory_total"]
        return int(value)
    except (FileNotFoundError, KeyError, ValueError, TypeError, json.JSONDecodeError):
        return None


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
    arg_path = Path(args.file_path)
    file_path = arg_path
    if is_info_file(str(file_path)):
        try:
            info_data = load_info_file(str(file_path))
            rel_usage_path = Path(info_data["output_paths"]["usage"])
            file_path = file_path.with_name(rel_usage_path.name)
        except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
            lgr.error("Error reading info file %s: %s", args.file_path, e)
            return 1
    host_memory_total = _load_host_memory_total(arg_path)

    try:
        data = load_usage_file(str(file_path))
    except FileNotFoundError:
        lgr.error("File %s was not found.", file_path)
        return 1
    except json.JSONDecodeError:
        lgr.error("File %s contained invalid JSON.", file_path)
        return 1

    try:
        pid_series = _build_pid_series(data, cpu_mode=args.cpu)
        totals_rss_xs, totals_rss_ys = _totals_rss_series(data)
    except KeyError as e:
        lgr.error("Usage file %s is missing required field: %s", file_path, e)
        return 1
    except ValueError as e:
        lgr.error("Usage file %s contains invalid data format: %s", file_path, e)
        return 1
    except Exception as e:
        lgr.error("Error processing usage file %s: %s", file_path, e)
        return 1

    fig, ax = plt.subplots()
    ax2 = ax.twinx()  # type: ignore[attr-defined]

    # Per-pid traces: dotted, faint, single color per metric. The cloud of
    # pid lines reads as background texture; the envelopes carry the signal.
    for s in pid_series.values():
        pdcpu_xs = [t for t, v in zip(s["elapsed"], s["cpu"]) if v is not None]
        pdcpu_ys = [v for v in s["cpu"] if v is not None]
        if pdcpu_xs:
            ax.plot(  # type: ignore[call-arg]
                pdcpu_xs,
                pdcpu_ys,
                color=PCPU_COLOR,
                linestyle=":",
                linewidth=0.8,
                alpha=0.4,
            )
        ax2.plot(  # type: ignore[call-arg]
            s["elapsed"],
            s["rss"],
            color=RSS_COLOR,
            linestyle=":",
            linewidth=0.8,
            alpha=0.4,
        )

    # Envelopes: max (lower bound) solid, upper bound dashed. If some pid
    # was at 50%, the total was at least 50% -- max-of-pids is a true lower
    # bound on the concurrent total in both metrics.
    #
    # Upper bounds differ by metric and (for cpu) by mode:
    #
    # - cpu, ps-cpu-timepoint: sum of per-pid pdcpu. A genuine upper bound
    #   on what the concurrent total could have been. Loose on multi-core
    #   boxes (it doesn't know about cores) but symmetric with the lower
    #   bound line.
    # - cpu, ps-pcpu: NO upper bound drawn. The per-pid value is ps's
    #   cumulative lifetime ratio, which inflates wildly for short-lived
    #   pids (e.g., a 0.01s pid that used 0.5s cputime reports pcpu=5000
    #   because etime is integer-rounded). Summing those per-pid maxes
    #   across pids that may not have coexisted at any single sub-sample
    #   compounds the inflation with phantom coexistence. The result
    #   ("sum=11000% on a 20-core box") is misleading enough that we'd
    #   rather render no upper bound than a wrong one. The per-pid cloud
    #   plus max-across-pids lower bound carry the signal.
    #
    # - rss: duct's per-record ``totals.rss``, i.e. the peak concurrent rss
    #   observed at any single sample in the report interval. Within
    #   "observed samples only" framing this is a true upper bound on
    #   sampled concurrent rss. We do NOT sum per-pid peaks for rss --
    #   that introduces phantom coexistence (pids whose peaks fell in
    #   different samples within the interval) and pads the line by gigs
    #   on bursty workloads.
    pcpu_xs, pcpu_max, pcpu_sum = _envelopes(pid_series, "cpu")
    if pcpu_xs:
        ax.plot(  # type: ignore[call-arg]
            pcpu_xs, pcpu_max, color=PCPU_COLOR, linestyle="-", linewidth=2.0
        )
        if args.cpu != CPU_MODE_PS_PCPU:
            ax.plot(  # type: ignore[call-arg]
                pcpu_xs, pcpu_sum, color=PCPU_COLOR, linestyle="--", linewidth=1.5
            )
    rss_xs, rss_max, _ = _envelopes(pid_series, "rss")
    if rss_xs:
        ax2.plot(  # type: ignore[call-arg]
            rss_xs, rss_max, color=RSS_COLOR, linestyle="-", linewidth=2.0
        )
    if totals_rss_xs:
        ax2.plot(  # type: ignore[call-arg]
            totals_rss_xs,
            totals_rss_ys,
            color=RSS_COLOR,
            linestyle="--",
            linewidth=1.5,
        )

    ax.set_xlabel("Elapsed Time")
    ax.set_ylabel(f"{args.cpu} (%)")
    ax2.set_ylabel("rss")
    if pid_series:
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
        rss_label = "rss"
        if host_memory_total is not None:
            rss_label = (
                f"rss (host: {SummaryFormatter().naturalsize(host_memory_total)})"
            )
        color_handles = [
            Line2D([0], [0], color=PCPU_COLOR, linewidth=2.0, label=args.cpu),
            Line2D([0], [0], color=RSS_COLOR, linewidth=2.0, label=rss_label),
        ]
        ax.legend(handles=color_handles, loc="upper left", fontsize=9)  # type: ignore[call-arg]

    ax.xaxis.set_major_formatter(  # type: ignore[attr-defined]
        HumanizedAxisFormatter(min_ratio=args.min_ratio, units=_TIME_UNITS)
    )
    ax2.yaxis.set_major_formatter(  # type: ignore[attr-defined]
        HumanizedAxisFormatter(min_ratio=args.min_ratio, units=FILESIZE_UNITS)
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
