"""Resource-usage plotting for con-duct.

The per-pid layout (per-pid pdcpu / pmem / rss lines) is modeled on
brainlife's smon task viewer:
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
DEFAULT_MIN_PEAK_PDCPU = 0.5
DEFAULT_MIN_PEAK_RSS = 10 * 1024 * 1024

# After filtering, cap the legend by taking the top-N pids: half by peak pdcpu
# and half by peak rss, unioned. Result is between N//2 and N pids depending
# on overlap. Set to None to keep all filtered pids.
DEFAULT_TOP_N: Optional[int] = 10

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


def _shorten_cmd(cmd: str, limit: int = 50) -> str:
    """Shorten a long cmd for legend display.

    Mirrors brainlife's ``shorten()`` (taskinfo.vue): tokens longer than 20
    chars get their last 20 kept after ``..``; final result is truncated to
    ``limit`` chars.
    """
    if len(cmd) < limit:
        return cmd
    parts = []
    for tok in cmd.split(" "):
        if len(tok) < 20:
            parts.append(tok)
        else:
            parts.append(".." + tok[-20:])
    short = " ".join(parts)
    if len(short) > limit:
        short = short[:limit] + "..."
    return short


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
    top_n: Optional[int] = DEFAULT_TOP_N,
    drop_ps_observer: bool = False,
) -> Dict[str, Dict[str, Any]]:
    """Trim per-pid series for legibility.

    A pid is kept if it is "notable" on either axis: peak pdcpu reaches
    ``min_peak_pdcpu`` *or* peak rss reaches ``min_peak_rss``. This way an
    idle process holding significant memory still appears on the chart.

    With ``top_n`` set, the legend is capped by combining two rankings:
    the top ``top_n // 2`` pids by peak pdcpu, plus the top ``top_n // 2``
    pids by peak rss, unioned. Result is between ``top_n // 2`` and
    ``top_n`` pids depending on overlap. This way "interesting on either
    axis" survives the cap without one metric squeezing out the other.

    With ``drop_ps_observer``, drops pids whose cmd starts with ``"ps "``.
    """
    out: Dict[str, Dict[str, Any]] = {}
    for pid, s in series.items():
        if drop_ps_observer and s["cmd"].startswith("ps "):
            continue
        if _peak_pdcpu(s) < min_peak_pdcpu and _peak_rss(s) < min_peak_rss:
            continue
        out[pid] = s
    if top_n is None or len(out) <= top_n:
        return out
    half = max(1, top_n // 2)
    by_pdcpu = sorted(out.items(), key=lambda kv: -_peak_pdcpu(kv[1]))
    by_rss = sorted(out.items(), key=lambda kv: -_peak_rss(kv[1]))
    keep_order = list(
        dict.fromkeys(
            [pid for pid, _ in by_pdcpu[:half]] + [pid for pid, _ in by_rss[:half]]
        )
    )
    return {pid: out[pid] for pid in keep_order}


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

    fig, ax1 = plt.subplots(  # type: ignore[call-overload]
        figsize=(20, 15), constrained_layout=True
    )
    ax2 = ax1.twinx()  # type: ignore[attr-defined]

    # Pick colors from the default cycle so pdcpu/pmem/rss for one pid all
    # share a color across the three line styles.
    color_cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]  # type: ignore[attr-defined]

    for i, (pid, s) in enumerate(filtered.items()):
        label = _shorten_cmd(s["cmd"]) or f"pid {pid}"
        color = color_cycle[i % len(color_cycle)]
        # pdcpu: drop None (no plot point at first-observation / etime=0).
        xs = [t for t, v in zip(s["elapsed"], s["pdcpu"]) if v is not None]
        ys = [v for v in s["pdcpu"] if v is not None]
        if xs:
            ax1.plot(xs, ys, label=label, color=color)
            # pmem: same axis, dotted, dimmed.
            ax1.plot(  # type: ignore[call-arg]
                s["elapsed"], s["pmem"], color=color, linestyle=":", alpha=0.5
            )
        else:
            # No pdcpu measurement (single sample / all-reuse / etime=0). Still
            # plot pmem so memory-only pids appear; attach the pid legend label
            # to the pmem line in this case.
            ax1.plot(  # type: ignore[call-arg]
                s["elapsed"],
                s["pmem"],
                label=label,
                color=color,
                linestyle=":",
                alpha=0.5,
            )
        # rss: secondary axis, dashed, dimmed.
        ax2.plot(  # type: ignore[call-arg]
            s["elapsed"], s["rss"], color=color, linestyle="--", alpha=0.5
        )
        # TODO: option to plot vsz alongside rss (commented out per #399 plot-fix scope).
        # ax2.plot(s["elapsed"], s["vsz"], color=color, linestyle="-.", alpha=0.5)

    ax1.set_xlabel("Elapsed Time")
    ax1.set_ylabel("pdcpu / pmem (%)")
    ax2.set_ylabel("rss")
    if filtered:
        # Linestyle key (small black mock lines) so a viewer can decode
        # solid/dotted/dashed without reading the axis labels. Added as an
        # artist so the per-pid legend below doesn't replace it.
        style_handles = [
            Line2D([0], [0], color="black", linestyle="-", label="pdcpu"),
            Line2D([0], [0], color="black", linestyle=":", label="pmem"),
            Line2D([0], [0], color="black", linestyle="--", label="rss"),
        ]
        style_legend = ax1.legend(  # type: ignore[call-arg]
            handles=style_handles, loc="upper right", fontsize=8
        )
        ax1.add_artist(style_legend)  # type: ignore[attr-defined]
        ax1.legend(loc="upper left", fontsize=8)  # type: ignore[call-arg]

    ax1.xaxis.set_major_formatter(  # type: ignore[attr-defined]
        HumanizedAxisFormatter(min_ratio=args.min_ratio, units=_TIME_UNITS)
    )
    ax2.yaxis.set_major_formatter(  # type: ignore[attr-defined]
        HumanizedAxisFormatter(min_ratio=args.min_ratio, units=_MEMORY_UNITS)
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
