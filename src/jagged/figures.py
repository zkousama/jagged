from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from jagged.analysis import Delta, load_trials, paired_delta
from jagged.metrics import reliability

STRATA = ["thin_unanimous", "well_attended", "contested"]
DPI = 200
PALETTE = ["#1b4d6e", "#c45c26", "#2f6b4f", "#6d4c7d", "#a67c2d", "#8b3a3a"]
DOSE_ARMS = [("baseline", 0), ("context_25", 25), ("context_50", 50), ("context_100", 100)]


def _style(ax, hide_left=False):
    ax.grid(False)
    sides = ("top", "right", "left") if hide_left else ("top", "right")
    for side in sides:
        ax.spines[side].set_visible(False)


def _save(fig, out) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return out


def degradation_curves(trials_path, out) -> Path:
    trials, _ = load_trials(trials_path)
    present = [s for s in STRATA if any(r["stratum"] == s for r in trials)]
    arms = sorted({r["arm"] for r in trials} - {"baseline", "placebo"})

    fig, ax = plt.subplots(figsize=(7, 4.5))
    if "placebo" in {r["arm"] for r in trials}:
        band = [paired_delta(trials, "baseline", "placebo", stratum=s) for s in present]
        ax.fill_between(range(len(present)),
                        [d.lo for d in band], [d.hi for d in band],
                        alpha=0.15, color=PALETTE[0], label="placebo band", zorder=1)
    for i, arm in enumerate(arms):
        pts = [paired_delta(trials, "baseline", arm, stratum=s) for s in present]
        ax.plot(range(len(present)), [d.point for d in pts], marker="o",
                color=PALETTE[i % len(PALETTE)], label=arm, zorder=3)
    ax.axhline(0, linewidth=1, color="#333", zorder=2)
    ax.set_xticks(range(len(present)))
    ax.set_xticklabels([s.replace("_", " ") for s in present])
    ax.set_xlabel("difficulty stratum")
    ax.set_ylabel("ΔAUC vs. docs-compliant baseline")
    ax.legend(frameon=False, fontsize=8)
    _style(ax)
    return _save(fig, out)


def forest_plot(deltas: dict[str, Delta], placebo: Delta, out) -> Path:
    arms = sorted(deltas, key=lambda a: deltas[a].point)
    fig, ax = plt.subplots(figsize=(7, 0.45 * len(arms) + 1.6))
    ax.axvspan(placebo.lo, placebo.hi, alpha=0.15, color=PALETTE[0],
               label="placebo band", zorder=1)
    ax.axvline(0, linewidth=1, color="#333", zorder=2)
    for y, arm in enumerate(arms):
        d = deltas[arm]
        color = PALETTE[y % len(PALETTE)]
        ax.plot([d.lo, d.hi], [y, y], linewidth=2, color=color, zorder=3)
        ax.plot([d.point], [y], marker="o", color=color, zorder=4)
    ax.set_yticks(range(len(arms)))
    ax.set_yticklabels(arms)
    ax.set_xlabel("ΔAUC vs. docs-compliant baseline (95% CI)")
    ax.legend(frameon=False, fontsize=8)
    _style(ax, hide_left=True)
    return _save(fig, out)


def reliability_diagram(trials_path, base_arm, worst_arm, out) -> Path:
    trials, _ = load_trials(trials_path)
    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    ax.plot([0, 1], [0, 1], linewidth=1, color="#888", zorder=1)
    for i, arm in enumerate((base_arm, worst_arm)):
        rows = [r for r in trials if r["arm"] == arm]
        bins = reliability([int(r["label"]) for r in rows],
                           [r["probability"] for r in rows])
        color = PALETTE[i]
        ax.plot([c for c, _, _ in bins], [a for _, a, _ in bins],
                marker="o", color=color, label=arm, zorder=3)
        for conf, acc, count in bins:
            ax.annotate(str(count), (conf, acc), textcoords="offset points",
                        xytext=(5, 5), fontsize=7, color=color)
    ax.set_xlabel("predicted probability")
    ax.set_ylabel("observed frequency")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.legend(frameon=False, fontsize=8)
    _style(ax)
    return _save(fig, out)


def dose_response(trials_path, out) -> Path:
    trials, _ = load_trials(trials_path)
    xs, ys, los, his = [], [], [], []
    for arm, frac in DOSE_ARMS:
        if arm != "baseline" and not any(r["arm"] == arm for r in trials):
            continue
        if arm == "baseline":
            xs.append(frac)
            ys.append(0.0)
            los.append(0.0)
            his.append(0.0)
            continue
        d = paired_delta(trials, "baseline", arm)
        xs.append(frac)
        ys.append(d.point)
        los.append(d.lo)
        his.append(d.hi)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.fill_between(xs, los, his, alpha=0.15, color=PALETTE[1], zorder=1)
    ax.plot(xs, ys, marker="o", color=PALETTE[1], zorder=3)
    ax.axhline(0, linewidth=1, color="#333", zorder=2)
    ax.set_xlabel("context fraction (%)")
    ax.set_ylabel("ΔAUC vs. docs-compliant baseline")
    _style(ax)
    return _save(fig, out)
