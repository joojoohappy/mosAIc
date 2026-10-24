"""Draw the charts in docs/engineering-case-study/ from benchmarks/results/*.json.

    apps/backend/.venv/bin/pip install -r benchmarks/requirements.txt
    apps/backend/.venv/bin/python benchmarks/charts.py

Every bar and point comes straight from a result file; nothing is typed in.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
OUT = HERE.parent / "docs" / "engineering-case-study" / "img"

# Reference categorical palette (light), fixed order.
BLUE, ORANGE, AQUA, YELLOW, MAGENTA = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": MUTED, "xtick.color": MUTED,
    "ytick.color": MUTED, "text.color": INK, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.8, "axes.axisbelow": True, "font.size": 10,
    "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
})


def load(name):
    return json.loads((RES / f"{name}.json").read_text())


def bars(ax, labels, series, unit, fmt="{:.0f}"):
    """Grouped bars with a 2px surface gap and value labels in text ink."""
    n = len(series)
    width = 0.8 / n
    for k, (name, values, color) in enumerate(series):
        xs = [i + (k - (n - 1) / 2) * width for i in range(len(labels))]
        rects = ax.bar(xs, values, width, color=color, label=name,
                       edgecolor=SURFACE, linewidth=2)
        for r, v in zip(rects, values, strict=False):
            ax.annotate(fmt.format(v), (r.get_x() + r.get_width() / 2, r.get_height()),
                        ha="center", va="bottom", fontsize=8, color=MUTED,
                        xytext=(0, 2), textcoords="offset points")
    ax.set_xticks(range(len(labels)), labels)
    ax.set_ylabel(unit)
    ax.grid(axis="x", visible=False)


def api_latency():
    d = load("api_latency_after")
    eps = list(dict.fromkeys(c["endpoint"] for c in d["cells"]))
    colors = [BLUE, ORANGE, AQUA, YELLOW, MAGENTA]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, metric, title in [(axes[0], "p50_ms", "p50"), (axes[1], "p99_ms", "p99")]:
        for ep, color in zip(eps, colors, strict=False):
            cells = [c for c in d["cells"] if c["endpoint"] == ep]
            levels = sorted({c["concurrency"] for c in cells})
            ys = [statistics.median(c[metric] for c in cells if c["concurrency"] == lv)
                  for lv in levels]
            ax.plot(levels, ys, marker="o", markersize=6, linewidth=2, color=color, label=ep)
        ax.set_xscale("log", base=2)
        ax.set_xticks([1, 8, 32], ["1", "8", "32"])
        ax.set_xlabel("concurrent clients (k6 VUs)")
        ax.set_ylabel(f"{title} latency, ms")
        ax.set_title(f"{title} (median of 3 × 1,000 requests)", fontsize=10, color=INK, loc="left")
    axes[1].legend(fontsize=8, loc="upper left")
    fig.suptitle("B1 · Read endpoints, one uvicorn worker, loopback", x=0.01, ha="left",
                 fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / "b1-read-latency.png", dpi=150)


def generate_overhead():
    base, after = load("generate_baseline"), load("generate_after")

    def p50(d):
        out = {}
        for c in d["overhead"]:
            out.setdefault(c["photo"], []).append(c["p50_ms"])
        return {k: statistics.median(v) for k, v in out.items()}

    b, a = p50(base), p50(after)
    labels = list(b)
    fig, ax = plt.subplots(figsize=(7, 3.8))
    bars(ax, labels, [("PR #2 (fbbc625)", [b[k] for k in labels], BLUE),
                      ("this branch", [a[k] for k in labels], ORANGE)], "p50 latency, ms",
         "{:.1f}")
    ax.set_title("B2 · MOSAIC's own cost per generate request\n(simulated provider, 0 s delay; "
                 "not Gemini latency)", fontsize=10, loc="left")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "b2-generate-overhead.png", dpi=150)


def reliability():
    base, after = load("reliability_baseline"), load("reliability_after")

    def drip(d):
        return next(r["wall_s"] for r in d["provider_failures"] if r["case"] == "drip")

    def dup_calls(d, case):
        return next(r["provider_calls"] for r in d["duplicates"] if r["case"] == case)

    def corrupt_reached(d):
        return sum(r["reached_provider"] for r in d["corrupt_uploads"]
                   if not r["case"].startswith("valid"))

    def race(d, key):
        rows = [r for r in d["budget_race"] if r["workers"] == 4]
        if key == "500s":
            return sum(v for r in rows for k, v in r["statuses"].items() if k.startswith("500"))
        return max(r["provider_calls"] for r in rows)

    panels = [
        ("Slow-drip provider:\nwall time with a 2 s timeout", "seconds",
         [drip(base)], [drip(after)], "{:.1f}"),
        ("Same photo sent twice,\n1 s apart: provider calls", "calls",
         [dup_calls(base, "1s apart (refresh + retry)")],
         [dup_calls(after, "1s apart (refresh + retry)")], "{:.0f}"),
        ("Damaged JPEGs (6) that\nreached the provider", "uploads",
         [corrupt_reached(base)], [corrupt_reached(after)], "{:.0f}"),
        ("4 workers × 5 trials:\nHTTP 500 responses", "responses",
         [race(base, "500s")], [race(after, "500s")], "{:.0f}"),
    ]
    fig, axes = plt.subplots(1, len(panels), figsize=(12, 3.6))
    for ax, (title, unit, b, a, fmt) in zip(axes, panels, strict=False):
        bars(ax, [""], [("PR #2", b, BLUE), ("this branch", a, ORANGE)], unit, fmt)
        ax.set_title(title, fontsize=9, loc="left")
        ax.set_xticks([])
        ax.margins(y=0.2)
    axes[0].legend(fontsize=8, loc="upper right")
    fig.suptitle("B3 · Reliability defects, before and after (simulated provider)", x=0.01,
                 ha="left", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / "b3-reliability.png", dpi=150)


def memory():
    d = load("generate_after")
    rows = d["memory"]
    fig, ax = plt.subplots(figsize=(6, 3.6))
    bars(ax, [str(r["concurrency"]) for r in rows],
         [("peak RSS", [r["rss_peak_mb"] for r in rows], BLUE)], "MB")
    ax.axhline(rows[0]["rss_idle_mb"], color=MUTED, linewidth=1, linestyle="--")
    ax.annotate(f"idle {rows[0]['rss_idle_mb']:.0f} MB", (0.98, rows[0]["rss_idle_mb"]),
                xycoords=("axes fraction", "data"), ha="right", va="bottom", fontsize=8,
                color=MUTED)
    ax.set_xlabel(f"generations in flight ({rows[0]['upload_mb']} MB upload each)")
    ax.set_title("B2 · Backend memory vs. in-flight generations", fontsize=10, loc="left")
    fig.tight_layout()
    fig.savefig(OUT / "b2-memory.png", dpi=150)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    api_latency()
    generate_overhead()
    reliability()
    memory()
    print("charts written to", OUT)
