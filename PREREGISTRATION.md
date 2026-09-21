# Pre-registration

This file is committed before any trial in the study is collected. The git
timestamp is the freeze. Results land in a later commit.

The study measures TypeSafe's documented failure modes for `jev-1.13`.
Baseline is the configuration the jaggedness page recommends. Each arm
breaks one piece of that advice. The estimand is a paired delta against
that baseline.

## Conditions

Baseline: state trimmed to `core`, arithmetic precomputed (numerics in
their `banded` form), dates resolved to relative phrasing, boundary cases
stated in the `criteria`, instructions and criteria aligned. The criteria
placement follows the page: state the exact condition in the
`instructions`, and put boundary cases in the criteria. A Noul takes
`criteria` as descriptions of its `true` and `false` cases.

| # | Mode | Arm | What changes |
|---|---|---|---|
| | (control) | `baseline` | docs-compliant configuration |
| 1 | Literal reading | `literal` | Boundary cases dropped from the criteria; intent left implicit |
| 2 | Math and Numbers | `numbers` | `banded` replaced with `raw` |
| 3 | Date and time comparison | `dates` | Relative phrasing replaced with raw ISO dates |
| 4 | Indirection | `indirection` | Semantically equivalent double negative |
| 5 | Large state full of irrelevant detail | `context_25`, `context_50`, `context_100` | `core` plus 25% / 50% / 100% of `context` |
| 6 | Adversarial content | `adversarial` | A directive injected into a `context` field |
| 7 | Contradictory instructions and criteria | `criteria` | Criteria polarity inverted against instructions |
| P | Placebo | `placebo` | State field order shuffled |

Eleven arms including baseline. Mode 5 is a dose-response; three points
make a curve.

Each arm is read on the question its manipulation reaches. Mode 3 is
scored on `window`, the only judgment here that consults a date.
Everything else is scored on `verdict`. Every arm is reported on both
questions. The decision rule counts the question named in this paragraph,
chosen here rather than after the deltas are in.

Mode 4's two phrasings have to be equivalent, or the arm measures a badly
worded question. Both are published verbatim so a reader can judge.

Mode 6 ships the injected-instruction shape. The page names two others
(a deliberately misleading framing, and text that argues for its own
classification). v1 names them rather than arming them.

Generation (mode 9) is out of scope. Common-sense structural invariants
(mode 8) are not an arm; they are the third noise floor, below.

v1 is Wikipedia Articles for Deletion. An OSV substrate is deferred.

## Labelling

Verdict-restricted, frozen here. The label is the closing administrator's
decision. `true` means the article was deleted. Only closes that parse as
`keep` or `delete` become items; every other close is counted and dropped.
A discussion without two parseable timestamps is dropped rather than
half-labelled, so mode 3 is scored on the same items as every other arm.

## Strata

Assigned by a rule fixed before any model call, from participation volume
and disagreement:

- `contested`: the close is no consensus
- `thin_unanimous`: keep or delete, three or fewer participants
- `well_attended`: keep or delete, more than three participants

Because labelling drops every close that is not keep or delete,
`contested` items are counted in the dropped tally and do not enter the
scored set. The pilot records whether the remaining two strata are usable.

Per-stratum deltas carry their own intervals. The headline is that
interaction.

## Metrics

Estimand: paired delta against baseline. Repeats average within item
first. Bootstrap over items: resample with replacement, recompute the
metric on both arms of the resampled set, take the difference. 2000
draws. 95% percentile interval.

Per arm and question:

- AUC, primary. A Noul returns a probability; thresholding discards it.
- Accuracy at 0.5, the documented cut.
- Calibration: expected calibration error, plus a reliability diagram.

Latency and token consumption are reported. They are not part of the
decision rule.

## Noise-floor procedure

Three floors.

1. Repeat variance. Identical requests, three times. If the model is
   deterministic this floor is zero; that is unknown as of writing, and
   the first thing the pilot measures.

2. Placebo. Field ordering is a change the docs give no reason to care
   about. Every real effect has to clear the placebo arm's interval. If
   shuffling moves results as much as the manipulations do, the effect
   sizes were noise.

3. Invariance probe, for `criteria` and `indirection` only. Mode 8's
   claim is that P(noul) and 1 - P(not noul) may not be directly
   comparable; the page's own example sums to 1.19. Those two arms
   invert polarity or route through a double negative, so they assume a
   complement behaves like a complement. The probe asks a judgment and
   its negation as separate Nouls on the same items. Its deviation from 1
   is the floor those two arms have to clear, on top of the placebo.

## Decision rule

An effect counts when all of these hold:

- its confidence interval excludes zero
- its magnitude clears the placebo arm's upper bound
- it survives Benjamini-Hochberg at q = 0.05 across the full family of
  arm deltas on their pre-registered primary questions
- its direction holds across repeats

`criteria` and `indirection` also have to clear the invariance-probe
floor.

Everything else is reported as null. Nulls are published with the same
prominence as positive findings. If padding costs nothing measurable,
that piece of the vendor's advice is folklore.

Accuracy, ECE, latency, token consumption and the per-stratum splits are
reported. They are not in the family the decision rule corrects.

## Pilot

A declared pilot of about 50 items sets thresholds that cannot be known
in advance: cost, whether two-decimal probabilities give usable
intervals, whether repeats agree, whether the two remaining strata can
be filled. The main run is 500 items from a disjoint set.

If the pilot forces a change to anything above, this file is updated in
a commit that lands before the main run, and the write-up records what
changed.
