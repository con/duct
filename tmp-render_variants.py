"""Render plot.py variants on the bundled tmp-logs/ files.

Part of the temporary demo commit (REVERT ME) -- not shipped with
the plot.py PR. Reuses ``plot._build_pid_series`` /
``plot._filter_pids`` so the data path matches the production CLI
output exactly.

Run from the worktree root:

    python tmp-render_variants.py
"""

from __future__ import annotations
from pathlib import Path
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from con_duct.json_utils import load_usage_file  # noqa: E402
from con_duct.plot import _build_pid_series, _filter_pids, _shorten_cmd  # noqa: E402

ROOT = Path(__file__).resolve().parent
LOGS = ROOT / "tmp-logs"
OUT = ROOT / "tmp-images"

DATASETS = [
    ("399", LOGS / "399-usage.json"),
    ("fmriprep", LOGS / "fmriprep_sub-CC0007_usage.jsonl"),
]


def _draw_combined(
    ax_pdcpu, ax_rss, filtered, *, with_pmem: bool, with_rss: bool
) -> None:
    for pid, s in filtered.items():
        label = _shorten_cmd(s["cmd"]) or f"pid {pid}"
        xs = [t for t, v in zip(s["elapsed"], s["pdcpu"]) if v is not None]
        ys = [v for v in s["pdcpu"] if v is not None]
        if not xs:
            continue
        (line,) = ax_pdcpu.plot(xs, ys, label=label)
        if with_pmem:
            ax_pdcpu.plot(
                s["elapsed"],
                s["pmem"],
                color=line.get_color(),
                linestyle=":",
                alpha=0.5,
            )
        if with_rss:
            ax_rss.plot(
                s["elapsed"],
                s["rss"],
                color=line.get_color(),
                linestyle="--",
                alpha=0.5,
            )


def render_combined(
    filtered, output: Path, title: str, *, with_pmem=True, with_rss=True
) -> None:
    fig, ax1 = plt.subplots(figsize=(20, 15))
    ax2 = ax1.twinx() if with_rss else None
    _draw_combined(ax1, ax2, filtered, with_pmem=with_pmem, with_rss=with_rss)
    ax1.set_xlabel("Elapsed time (s)")
    ax1.set_ylabel("pdcpu" + (" / pmem" if with_pmem else "") + " (%)")
    if ax2 is not None:
        ax2.set_ylabel("rss (bytes)")
    if filtered:
        ax1.legend(loc="upper left", fontsize=6, ncol=2)
    ax1.set_title(title)
    ax1.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output, dpi=110)
    plt.close(fig)


def render_stack_split(filtered, output: Path, title: str) -> None:
    """Brainlife-style: three stacked-area panels (pdcpu, pmem, rss)."""
    # Union of every per-pid elapsed timepoint -> master x grid.
    all_x = sorted({t for s in filtered.values() for t in s["elapsed"]})
    if not all_x:
        return
    pdcpu_rows, pmem_rows, rss_rows, labels = [], [], [], []
    for pid, s in filtered.items():
        idx = {t: i for i, t in enumerate(s["elapsed"])}
        pd = [
            (s["pdcpu"][idx[t]] if t in idx and s["pdcpu"][idx[t]] is not None else 0.0)
            for t in all_x
        ]
        pm = [(s["pmem"][idx[t]] if t in idx else 0.0) for t in all_x]
        rs = [(s["rss"][idx[t]] if t in idx else 0.0) for t in all_x]
        pdcpu_rows.append(pd)
        pmem_rows.append(pm)
        rss_rows.append(rs)
        labels.append(_shorten_cmd(s["cmd"]) or f"pid {pid}")
    fig, axes = plt.subplots(3, 1, figsize=(20, 15), sharex=True)
    ax_p, ax_m, ax_r = axes
    ax_p.stackplot(all_x, *pdcpu_rows, labels=labels, alpha=0.85)
    ax_m.stackplot(all_x, *pmem_rows, alpha=0.85)
    ax_r.stackplot(all_x, *rss_rows, alpha=0.85)
    ax_p.set_ylabel("pdcpu (%, stacked)")
    ax_m.set_ylabel("pmem (%, stacked)")
    ax_r.set_ylabel("rss (stacked)")
    ax_r.set_xlabel("Elapsed time (s)")
    if labels:
        ax_p.legend(loc="upper right", fontsize=6, ncol=2)
    for ax in axes:
        ax.grid(True, alpha=0.3)
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(output, dpi=110)
    plt.close(fig)


def render_split(filtered, output: Path, title: str) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(20, 15), sharex=True)
    ax_p, ax_m, ax_r = axes
    for pid, s in filtered.items():
        label = _shorten_cmd(s["cmd"]) or f"pid {pid}"
        xs = [t for t, v in zip(s["elapsed"], s["pdcpu"]) if v is not None]
        ys = [v for v in s["pdcpu"] if v is not None]
        if not xs:
            continue
        (line,) = ax_p.plot(xs, ys, label=label)
        color = line.get_color()
        ax_m.plot(s["elapsed"], s["pmem"], color=color)
        ax_r.plot(s["elapsed"], s["rss"], color=color)
    ax_p.set_ylabel("pdcpu (%)")
    ax_m.set_ylabel("pmem (%)")
    ax_r.set_ylabel("rss (bytes)")
    ax_r.set_xlabel("Elapsed time (s)")
    if filtered:
        ax_p.legend(loc="upper right", fontsize=6, ncol=2)
    for ax in axes:
        ax.grid(True, alpha=0.3)
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(output, dpi=110)
    plt.close(fig)


def main() -> None:
    variants = [
        # (filename, title, filter kwargs, render fn, render kwargs)
        (
            "01_default.png",
            "v1: default (notable pdcpu/rss, top 10 hybrid) - all-on-one",
            {},
            render_combined,
            {},
        ),
        (
            "02_top_5.png",
            "v2: tighter cap (top 5 hybrid)",
            dict(top_n=5),
            render_combined,
            {},
        ),
        (
            "03_top_20.png",
            "v3: looser cap (top 20 hybrid)",
            dict(top_n=20),
            render_combined,
            {},
        ),
        (
            "04_no_cap.png",
            "v4: no top_n cap (all notable pids)",
            dict(top_n=None),
            render_combined,
            {},
        ),
        (
            "05_pdcpu_only.png",
            "v5: pdcpu lines only (no pmem, no rss) - default cap",
            {},
            render_combined,
            dict(with_pmem=False, with_rss=False),
        ),
        (
            "06_split_subplots.png",
            "v6: separate subplots per metric - default cap",
            {},
            render_split,
            {},
        ),
        (
            "07_top_40.png",
            "v7: top 40 hybrid",
            dict(top_n=40),
            render_combined,
            {},
        ),
        (
            "08_stack_split.png",
            "v8: brainlife-style stacked area per metric - default cap",
            {},
            render_stack_split,
            {},
        ),
    ]

    for label, usage_path in DATASETS:
        if not usage_path.exists():
            print(f"skip {label}: missing {usage_path}")
            continue
        data = load_usage_file(str(usage_path))
        series = _build_pid_series(data)
        print(f"\n[{label}] {len(data)} records, {len(series)} unique pids")
        for fname_suffix, title, filter_kw, render_fn, render_kw in variants:
            filtered = _filter_pids(series, **filter_kw)
            out = (
                OUT
                / f"{fname_suffix.split('_', 1)[0]}_{label}_{fname_suffix.split('_', 1)[1]}"
            )
            render_fn(filtered, out, f"[{label}] {title}", **render_kw)
            print(
                f"  wrote {out.name}  ({len(filtered)} pids, {out.stat().st_size:,} bytes)"
            )


if __name__ == "__main__":
    main()
