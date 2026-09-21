import argparse
import sys
from pathlib import Path

from jagged.analysis import (SECONDARY_METRIC, benjamini_hochberg, family_deltas,
                             load_trials, paired_delta, question_for, verdict)
from jagged.conditions import ARM_NAMES


def _cmd_run(args) -> int:
    from jagged.client import JevClient
    from jagged.runner import run
    from jagged.substrates.afd import AfdSubstrate
    from jagged.wiki import WikiClient

    sub = AfdSubstrate(WikiClient(Path(args.cache) / "wiki"))
    items = sub.load(budget=args.items, dates=args.dates)
    print(f"loaded {len(items)} items; dropped {dict(sub.dropped)}")
    client = JevClient(model=args.model)
    try:
        out = run(items, sub.questions(), ARM_NAMES, repeats=args.repeats,
                  client=client, out_path=Path(args.out),
                  cache=Path(args.cache) / "jev", seed=args.seed, model=args.model)
    finally:
        client.close()
    print(f"wrote {out}")
    return 0


def _cmd_analyze(args) -> int:
    trials, dropped = load_trials(args.trials)
    print(f"{len(trials)} trials, {dropped} errored")
    family = family_deltas(trials, n_boot=args.n_boot)
    arms = sorted({arm for arm, _ in family})
    pvals = [0.001 if (d.lo > 0 or d.hi < 0) else 0.5 for d in family.values()]
    survived = benjamini_hochberg(pvals, q=0.05)
    for (key, d), ok in zip(family.items(), survived):
        arm, metric = key
        placebo = family.get(("placebo", metric))
        tag = verdict(d, placebo, ok) if placebo is not None else "n/a"
        print(f"{arm:14} [{question_for(arm):7}] {metric:8} {d.point:+.3f} "
              f"[{d.lo:+.3f}, {d.hi:+.3f}]  {tag}")
    print("secondary (not in the FDR family)")
    for arm in arms:
        d = paired_delta(trials, "baseline", arm, metric=SECONDARY_METRIC,
                         question=question_for(arm), n_boot=args.n_boot)
        print(f"{arm:14} [{question_for(arm):7}] {SECONDARY_METRIC:8} {d.point:+.3f} "
              f"[{d.lo:+.3f}, {d.hi:+.3f}]")
    Path(args.out).mkdir(parents=True, exist_ok=True)
    return 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(prog="jagged")
    subs = parser.add_subparsers(dest="cmd")

    r = subs.add_parser("run")
    r.add_argument("--substrate", default="afd")
    r.add_argument("--items", type=int, default=500)
    r.add_argument("--repeats", type=int, default=3)
    r.add_argument("--dates", nargs="*", default=None)
    r.add_argument("--model", default="jev-1.13")
    r.add_argument("--seed", type=int, default=1)
    r.add_argument("--out", default="data/trials/afd.jsonl")
    r.add_argument("--cache", default="data/cache")
    r.set_defaults(fn=_cmd_run)

    a = subs.add_parser("analyze")
    a.add_argument("--trials", default="data/trials/afd.jsonl")
    a.add_argument("--out", default="figures")
    a.add_argument("--n-boot", type=int, default=2000)
    a.set_defaults(fn=_cmd_analyze)

    # argparse exits the process on a bad command line. A main() that returns
    # its code instead is testable, and the code is the one argparse chose.
    try:
        args = parser.parse_args(argv)
    except SystemExit as exit_:
        return int(exit_.code or 0)
    if not getattr(args, "fn", None):
        parser.print_usage()
        return 2
    return args.fn(args)
