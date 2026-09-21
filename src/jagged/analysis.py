import collections
import json
from pathlib import Path

import numpy as np
from msgspec import Struct

from jagged.metrics import accuracy_at, auc, ece

METRICS = {"auc": auc, "accuracy": accuracy_at, "ece": ece}

# Which question carries each arm's primary delta. Only the dates arm manipulates
# something the window judgment reads, so it is the only one scored there. Every
# arm is reported on both questions; this is which one the decision rule counts.
PRIMARY_QUESTION = {"dates": "window"}
DEFAULT_QUESTION = "verdict"

# Co-primary after the declared pilot. Attempt 2 sat at verdict AUC 0.997 because
# the votes were in the state; design B still ranks at the ceiling, so AUC cannot
# show a degradation. Accuracy at 0.5 and ECE still moved. AUC stays computed and
# reported, and is not in the family Benjamini-Hochberg corrects.
PRIMARY_METRICS = ("accuracy", "ece")
SECONDARY_METRIC = "auc"


def question_for(arm: str) -> str:
    return PRIMARY_QUESTION.get(arm, DEFAULT_QUESTION)


class Delta(Struct, frozen=True):
    point: float
    lo: float
    hi: float


def load_trials(path) -> tuple[list[dict], int]:
    rows, dropped = [], 0
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("error") or row.get("probability") is None:
            dropped += 1
        else:
            rows.append(row)
    return rows, dropped


def collapse_repeats(trials: list[dict]) -> dict[tuple[str, str], dict]:
    buckets: dict[tuple[str, str], list[dict]] = collections.defaultdict(list)
    for row in trials:
        buckets[(row["arm"], row["item_id"])].append(row)
    out = {}
    for key, rows in buckets.items():
        out[key] = {"probability": float(np.mean([r["probability"] for r in rows])),
                    "label": rows[0]["label"], "stratum": rows[0]["stratum"]}
    return out


def paired_delta(trials, base_arm: str, arm: str, metric: str = "auc",
                 n_boot: int = 2000, seed: int = 1, stratum: str | None = None,
                 question: str | None = None) -> Delta:
    if question is not None:
        trials = [r for r in trials if r.get("question") == question]
    collapsed = collapse_repeats(trials)
    items = sorted({i for (a, i) in collapsed if a == base_arm}
                   & {i for (a, i) in collapsed if a == arm})
    if stratum:
        items = [i for i in items if collapsed[(base_arm, i)]["stratum"] == stratum]
    if not items:
        raise ValueError(
            f"paired_delta: no overlapping items for {base_arm!r} vs {arm!r} "
            f"(question={question!r}, stratum={stratum!r})"
        )
    fn = METRICS[metric]

    def score(sample, which):
        labels = [collapsed[(which, i)]["label"] for i in sample]
        probs = [collapsed[(which, i)]["probability"] for i in sample]
        return fn(labels, probs)

    point = score(items, arm) - score(items, base_arm)
    rng = np.random.default_rng(seed)
    idx = np.arange(len(items))
    draws = []
    for _ in range(n_boot):
        sample = [items[j] for j in rng.choice(idx, size=len(idx), replace=True)]
        d = score(sample, arm) - score(sample, base_arm)
        if not np.isnan(d):
            draws.append(d)
    lo, hi = np.percentile(draws, [2.5, 97.5]) if draws else (float("nan"),) * 2
    return Delta(point=float(point), lo=float(lo), hi=float(hi))


def family_deltas(trials, n_boot: int = 2000, seed: int = 1) -> dict[tuple[str, str], Delta]:
    """Paired deltas for every non-baseline arm × both primary metrics.

    That product is the family Benjamini-Hochberg corrects. Placebo lives in it
    so its interval is the noise floor on the same metric the arm is judged on.
    """
    arms = sorted({r["arm"] for r in trials} - {"baseline"})
    out: dict[tuple[str, str], Delta] = {}
    for arm in arms:
        question = question_for(arm)
        for metric in PRIMARY_METRICS:
            out[(arm, metric)] = paired_delta(
                trials, "baseline", arm, metric=metric, n_boot=n_boot,
                seed=seed, question=question)
    return out


def benjamini_hochberg(pvalues: list[float], q: float = 0.05) -> list[bool]:
    n = len(pvalues)
    order = sorted(range(n), key=lambda i: pvalues[i])
    out = [False] * n
    largest = -1
    for rank, i in enumerate(order, start=1):
        if pvalues[i] <= q * rank / n:
            largest = rank
    for rank, i in enumerate(order, start=1):
        if rank <= largest:
            out[i] = True
    return out


def verdict(delta: Delta, placebo: Delta, survived_fdr: bool) -> str:
    """An effect must exclude zero, clear the placebo band, and survive FDR."""
    excludes_zero = (delta.lo > 0) or (delta.hi < 0)
    clears_placebo = abs(delta.point) > max(abs(placebo.lo), abs(placebo.hi))
    return "effect" if (excludes_zero and clears_placebo and survived_fdr) else "null"
