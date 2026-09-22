"""Ask the verdict both ways round: was the article deleted, and was it kept.

The pre-registered invariance probe (PREREGISTRATION.md, noise floor 3), run after
the main results were in. Mode 8 on TypeSafe's page says P(noul) and 1 - P(not noul)
may not be directly comparable; its own example sums to 1.19. The criteria and
indirection arms both invert the question, so part of their effect could be that
alone. This measures how much asking the plain opposite moves things.

Each call carries the baseline state and the baseline questions, plus one more: the
verdict reworded to ask whether the article was kept, with the criteria's sides
swapped to match. The instructions and criteria agree, and there's no double
negative, so the only change is which way round the question is asked. Both
questions share a call, so they read identical state. 3 repeats, as the main run.

    uv run python scripts/invariance_probe.py run     # needs AI_GATEWAY_API_KEY
    uv run python scripts/invariance_probe.py table   # reads the saved responses

`run` appends every request and response to data/followup/invariance.jsonl as it
goes, so an interrupted run picks up where it stopped, then compresses it to
data/followup/invariance.jsonl.gz.
"""

import argparse
import collections
import gzip
import json
import time
from pathlib import Path

REPEATS = 3
PARTIAL = Path("data/followup/invariance.jsonl")
OUT = Path("data/followup/invariance.jsonl.gz")


def _specs():
    from jagged.question import QuestionSpec
    from jagged.substrates.afd import AfdSubstrate

    specs = AfdSubstrate(client=None).questions()
    verdict = specs["verdict"]
    specs["kept"] = QuestionSpec(
        instructions=(
            "The state describes a Wikipedia deletion discussion. "
            "Answer whether the article was kept."
        ),
        criteria={"true": verdict.criteria["false"], "false": verdict.criteria["true"]},
        boundary=verdict.boundary,
        boundary_key="true",
    )
    return specs


def _items():
    """Every main-run item, once, with its baseline state and label."""
    out = {}
    for line in gzip.open("data/trials/afd.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(line)
        if r["arm"] == "baseline" and r["question"] == "verdict" and r["item_id"] not in out:
            out[r["item_id"]] = {"item_id": r["item_id"], "label": r["label"],
                                 "stratum": r["stratum"], "state": r["request"]["state"]}
    return list(out.values())


def run() -> None:
    import httpx

    from jagged.client import JevClient

    specs = _specs()
    items = _items()
    done = set()
    if PARTIAL.exists():
        for line in PARTIAL.open(encoding="utf-8"):
            row = json.loads(line)
            if not row["error"]:
                done.add((row["item_id"], row["repeat"]))
    client = JevClient()

    def ask(state):
        error = None
        for attempt in range(6):
            time.sleep(2.4)
            try:
                return client.ask(state, specs), attempt
            except httpx.HTTPStatusError as exc:
                error = exc
                if exc.response.status_code not in (429, 503, 504, 529):
                    break
            except httpx.TransportError as exc:
                error = exc
            time.sleep(5 * (attempt + 1))
        return error, attempt

    PARTIAL.parent.mkdir(parents=True, exist_ok=True)
    with PARTIAL.open("a", encoding="utf-8") as fh:
        for repeat in range(REPEATS):
            for item in items:
                if (item["item_id"], repeat) in done:
                    continue
                answers, retries = ask(item["state"])
                ok = isinstance(answers, dict)
                fh.write(json.dumps({
                    "item_id": item["item_id"],
                    "repeat": repeat,
                    "label": item["label"],
                    "stratum": item["stratum"],
                    "request": {"state": item["state"],
                                "questions": {k: s.to_noul() for k, s in specs.items()}},
                    "probabilities": ({k: a.probability for k, a in answers.items()}
                                      if ok else None),
                    "response": next(iter(answers.values())).raw if ok else None,
                    "retries": retries,
                    "error": None if ok else repr(answers),
                }, ensure_ascii=False) + "\n")
                fh.flush()
    client.close()
    with PARTIAL.open("rb") as src, gzip.open(OUT, "wb") as dst:
        dst.write(src.read())
    table()


def _rows():
    path = OUT if OUT.exists() else PARTIAL
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh]


def table() -> None:
    import numpy as np

    from jagged.analysis import paired_delta

    rows = [r for r in _rows() if r["probabilities"]]
    errored = len(_rows()) - len(rows)
    by_item = collections.defaultdict(list)
    for r in rows:
        by_item[r["item_id"]].append(r)
    deleted = {i: np.mean([r["probabilities"]["verdict"] for r in rs]) for i, rs in by_item.items()}
    kept = {i: np.mean([r["probabilities"]["kept"] for r in rs]) for i, rs in by_item.items()}
    sums = np.array([deleted[i] + kept[i] for i in by_item])

    print(f"{len(by_item)} items, {len(rows)} calls, {errored} errored")
    print(f"P(deleted) + P(kept): mean {sums.mean():.3f}, median {np.median(sums):.3f}, "
          f"5th to 95th percentile {np.percentile(sums, 5):.3f} to {np.percentile(sums, 95):.3f}")
    print(f"mean distance from 1: {np.abs(sums - 1).mean():.3f}; "
          f"within 0.05 of 1: {np.mean(np.abs(sums - 1) <= 0.05):.1%}")

    # The kept answer, turned round, scored against the deleted one as if it were
    # another arm: the same paired bootstrap, metrics and item averaging as the
    # main run.
    trials = []
    for r in rows:
        base = {"item_id": r["item_id"], "label": r["label"], "stratum": r["stratum"],
                "question": "verdict", "repeat": r["repeat"]}
        trials.append({**base, "arm": "asked_deleted", "probability": r["probabilities"]["verdict"]})
        trials.append({**base, "arm": "asked_kept", "probability": 1 - r["probabilities"]["kept"]})
    for metric in ("accuracy", "ece"):
        d = paired_delta(trials, "asked_deleted", "asked_kept", metric=metric)
        print(f"asked the other way round, {metric:8} {d.point:+.3f} [{d.lo:+.3f}, {d.hi:+.3f}]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["run", "table"])
    {"run": run, "table": table}[parser.parse_args().mode]()
