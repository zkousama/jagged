# Measuring jev-1.13's documented failure modes

Design spec. 2026-09-17.

## 1. The question

TypeSafe publishes a page listing eight ways jev-1.13 degrades, and for each one it
prescribes a remedy: trim the state, move arithmetic into code, resolve dates before you
ask, phrase instructions directly, keep criteria aligned with instructions. The page is
prose. No magnitudes, no conditions, no indication of which remedies matter.

This project measures them. Baseline is the configuration the docs recommend. Each
condition violates exactly one piece of that advice. The result is a per-mode cost, broken
out by input difficulty.

Framed as a question: **if you follow TypeSafe's guidance and set aside one piece of it at a
time, which pieces change the answer?**

TypeSafe publishes its failure modes on an open page, and the study is built from it. The
control is their own recommended configuration, so every result reads as advice for anyone
building on Jev.

## 2. Scope

In: seven of the eight documented modes, two substrates, one model version.

Out:
- **Generation** (mode 8). Jev isn't trained to generate and the docs say so. Testing it
  would be theatre. Stated in the write-up rather than faked.
- **Comparisons against other models.** Four ecosystem repos already do Jev-vs-baseline.
  This measures Jev against its own documentation.
- **Absolute capability claims.** "Jev is X% accurate at deletion debates" is not a result
  this design can support, and the write-up should not imply it. The estimand is a delta.

## 3. The item contract

A manipulation has to know what role a field plays, not just its value. Padding the state
with irrelevant detail is only a generic operation if the substrate has already declared
which fields the judgment legitimately needs.

```python
class Dual(Struct):
    raw: str        # "4.2.1 vs >=4.0.0 <4.17.21", or an ISO date
    banded: str     # "two minor versions before the fix"

class Item(Struct):
    id: str
    core: dict[str, str]        # fields the judgment needs
    context: dict[str, str]     # real, present, decision-irrelevant -> padding probe
    numeric: dict[str, Dual]    # tagged, so numeric<->semantic is mechanical
    temporal: dict[str, Dual]   # same, for date<->relative
    label: bool                 # ground truth
    stratum: str                # difficulty band
```

Temporal fields carry **both** forms for the same reason numeric ones do. An earlier
draft typed them as a bare ISO string, which made the baseline omit dates entirely and
turned mode 3 into a test of whether adding a field hurts rather than whether its
representation matters. A manipulation that changes presence is not a manipulation of
representation.

`banded` is load-bearing. It's what lets the same question be asked numerically and
semantically over identical items, which is the whole of mode 2.

```python
class Substrate(Protocol):
    name: str
    def load(self, budget: int) -> list[Item]: ...
    def question(self) -> Question: ...   # the baseline Noul, un-manipulated
```

Two constraints belong in the interface rather than in discipline:

- **Adapters never see the conditions.** They can't tailor items to flatter a manipulation.
- **`stratum` is assigned by a rule fixed before any model call.** Difficulty cannot be
  redefined after seeing results.

## 4. Substrates

### 4.1 Wikipedia Articles for Deletion (v1)

Every AfD is a public page under `Wikipedia:Articles for deletion/<title>` in namespace 4,
carrying the full argument thread and an administrator's closing decision. The archive runs
about twenty years deep. Closed discussions are wrapped in a `xfd-closed` boilerplate block.

The task is applying a written rule corpus (WP:N, WP:GNG, WP:NOT) to a messy human
argument, which puts **literal reading** — instruction-following, not arithmetic — at the
centre. That's the most interesting of the eight modes and the one every Jev integration is
implicitly betting on.

- `core`: nomination rationale, article summary, the policies actually cited
- `context`: boilerplate, signatures, thread furniture, procedural chatter
- `numeric`: participation counts, source counts
- `temporal`: nomination and close dates
- `label`: the closing decision (see the labelling choice below)
- `stratum`: participation volume and disagreement, banded

**Confound, and the labelling choice.** AfD outcomes partly reflect who showed up, not only
the merits, so raw outcome prediction is partly social-dynamics prediction. Two candidate
labellings address this, and exactly one is frozen at pre-registration:

- **Verdict, restricted.** The closing decision, on unanimous closes only. Simpler to parse,
  and unanimity strips most of the social variance.
- **Policy basis.** Whether the policy the closing admin cited actually applies. Closer to
  the judgment being tested, and harder to extract reliably.

Verdict-restricted is the default unless the pilot shows unanimous closes are too scarce or
too easy to stratify usefully. The write-up states the confound either way.

**To verify during implementation:** the exact close-template syntax and how reliably the
result string parses. Observed `xfd-closed` and the Afd-top boilerplate on a sampled page;
the parse itself is unproven.

### 4.2 OSV security advisories (v1.1)

Machine-checkable affected ranges, confirmed present in the API as SEMVER events of the
form `{"introduced": "4.0.0"}, {"fixed": "4.17.21"}`. Ground truth is objective and
computable, which makes this the cleanest available probe of the boundary between semantics
and arithmetic. "Is 4.2.1 affected?" reads as a semantic question and is arithmetic
underneath.

- `core`: advisory summary, ecosystem, package
- `context`: advisory prose, references, credits
- `numeric`: the version comparison itself
- `label`: computed from the published range
- `stratum`: version distance from the boundary

**Risk.** This may confirm the docs rather than surprise. "Not a calculator, as documented"
is not a finding. It becomes one only if the falloff has a shape — intact across major
versions, collapsing at patch level, or wherever the edge turns out to sit. That shape is
the deliverable, and the write-up should say so up front rather than oversell.

## 5. Conditions

Baseline is the docs-compliant configuration: state trimmed to `core`, arithmetic
precomputed, dates resolved to relative phrasing, boundary cases stated in the `criteria`,
instructions and criteria aligned. The criteria placement is the docs' own wording — "state
the exact condition in the `instructions`. Be specific. Put boundary cases in the criteria"
— and a Noul takes `criteria` as descriptions of its `true` and `false` cases, so the
boundary has somewhere to live that isn't the instruction string.

| # | Mode | Condition (one variable changed) |
|---|---|---|
| 1 | Literal reading | Boundary cases dropped from the criteria, intent left implicit |
| 2 | Math and Numbers | `banded` replaced with `raw` |
| 3 | Date and time comparison | Relative phrasing replaced with raw ISO dates |
| 4 | Indirection | Semantically equivalent double negative |
| 5 | Large state full of irrelevant detail | `core` + 25% / 50% / 100% of `context` |
| 6 | Adversarial content | Directive injected into a `context` field |
| 7 | Contradictory instructions and criteria | Criteria polarity inverted against instructions |
| P | Placebo | State field order shuffled |

Numbers and names in that table are the page's own, in the page's order. The study sets aside
one piece of TypeSafe's advice at a time, so the mapping to their list has to be checkable at
a glance.

Mode 5 is a dose-response rather than on/off, because three points make a curve.

**Mode 4 needs care.** The direct and double-negative phrasings must be genuinely
equivalent or the arm measures comprehension of a badly worded question instead of
indirection. Both phrasings are human-reviewed and published verbatim so readers can judge.

**Mode 6 has three shapes and AfD supplies a second one free.** The page names them:
"an injected instruction, a deliberately misleading framing, or text that argues for its own
classification". The arm above is the first. The third is what a deletion debate *is* —
editors arguing a classification, in the real corpus, already labelled — so it costs an arm
rather than a corpus. v1 ships the injection and names the other two; promoting either to its
own arm takes the cross product from 11 to 12.

Worth noting for the write-up: the remedy the page prescribes for this mode is "write precise
prompts, and test edge cases before deploying", which is advice to test rather than a
mitigation. It's the weakest of the eight, and this is the one arm measuring a failure its
own documentation has no answer for.

**The placebo is the second noise floor.** Field ordering is a change the docs give no
reason to care about. Every real effect must clear it. If shuffling moves results as much
as the manipulations do, the effect sizes were noise — and that is itself the better
finding.

Repeat variance is the first floor: identical calls, three times, to establish whether the
model is deterministic at all. Unknown as of writing.

## 6. The runner

**Cache key is `(request_hash, repeat_index)`.** Repeats are identical requests by
definition, so a plain request hash collapses them into one entry and silently reports
cache hits as perfect model agreement, destroying the variance estimate.

**Interleave arms.** Randomize trial order across the whole cross product. Running arm by
arm confounds arm with wall-clock time, and an early-access API days after launch will have
deploys and load swings under it.

**Failures are rows, not omissions.** Every errored trial records its error; analysis
reports completion rate per arm. This is concrete here: mode 5 at 100% context can exceed the
documented limit, so the arm most likely to fail is the one under measurement. Dropping those
silently would make padding look free. Adapters cap context to stay under the limit and the
runner records every truncation.

The limit is "64k tokens together for all `state` and `questions`; 32k tokens for the `state` +
the longest `question`". It is not a ceiling on state alone, so the cap has to be computed
against state plus the rendered question or the padding arm will fail at a threshold the
adapter thinks it's below.

**Trial record** — the publishable artifact:

```
trial_id, substrate, item_id, stratum, arm, repeat,
request_hash, request (verbatim), response (verbatim),
probability, label, latency_ms, error,
model, sdk_version, run_id, git_commit, ts
```

Verbatim request and response are what make "recompute my numbers without an API key" true.

**Run manifest** pins model version, SDK version, selection seed and git commit. The
jaggedness page is versioned at `jev-1.13`; these results expire with it.

**Budget.** Roughly 500 items x 11 arms x 3 repeats ~ 16k calls per substrate. Pinned as
config. Jev is early access with no public pricing, so cost is an unknown to measure during
the pilot rather than estimate now.

## 7. Analysis

**Estimand: paired delta against baseline.** Bootstrap over items — resample with
replacement, recompute the metric in both arms on the resampled set, take the difference.
Repeats average within item first.

**Metrics per arm:**
- AUC, primary. Noul returns a probability; thresholding discards information.
- Accuracy at 0.5, because that's the documented cut and what people will ship.
- Calibration: ECE plus reliability diagram.

**Calibration is the most likely real finding.** A Noul returns no confidence value; the docs
say plainly that "Noul does not return a separate confidence value", because the noul *is* the
probability that the answer is yes. Confidence is a Choice and Score statistic. So the number
this study calibrates is the only number Jev gives you, and the only published guidance on
trusting it is to "test with your own data, and adjust as you observe results". Nobody has
published that test. The question worth asking is whether calibration degrades while accuracy
holds. A model that
stays accurate but grows overconfident under state padding is more dangerous than one that
visibly degrades, because every downstream confidence gate stops working with nothing
looking wrong.

**Decision rule, pre-registered.** An effect counts when its CI excludes zero, its magnitude
clears the placebo arm's upper bound, it survives Benjamini-Hochberg at q=0.05 across the
full family, and its direction holds across repeats. Everything else is reported as null.

**Nulls get equal billing.** If padding costs nothing measurable, that piece of advice doesn't
change the answer on this task, and the write-up reports it. Pre-committing to publish nulls
is what makes the positive findings believable.

**The headline is an interaction.** Per-stratum deltas with their own intervals. "Padding
costs nothing on easy items and eighteen points on hard ones" is a difference-of-differences
and needs its own CI. Pooled averages erase the unevenness the jaggedness page claims.

**Cross-substrate replication, stated modestly.** Sign and rough magnitude agreeing across
AfD and OSV is suggestive of a model property rather than a prompt artifact. Two substrates
is not enough to call it general, and the write-up says so rather than letting readers
infer more.

**Figures:**
1. dAUC by stratum, one line per mode — the degradation curves
2. Reliability diagram, baseline against worst arm — the calibration result
3. Dose-response for context padding at 25/50/100%
4. Forest plot of every delta with CIs and the placebo band drawn in

Latency comes free and is worth reporting; speed is Jev's pitch and nobody has measured
what padding costs in milliseconds.

## 8. Pre-registration and the pilot

`PREREGISTRATION.md` is committed before the first main run: conditions, metrics, stratum
definitions, noise-floor procedure, decision rule. Git history timestamps it. Results land
in a later commit.

**The pilot is declared, not hidden.** A small run is needed to set thresholds and shake out
plumbing, and pretending otherwise falls apart under questioning. Pilot on ~50 items, freeze
the registration, then run the main study on a disjoint set. "We piloted on 50, changed X
and Y, then froze and ran on 500 fresh items" reads as more trustworthy than claiming a
cold start.

## 9. Repo

```
jagged/
|- PREREGISTRATION.md
|- README.md                   findings, figures, how to re-run
|- src/jagged/
|  |- items.py                 Item, Numeric
|  |- substrate.py             the Protocol
|  |- substrates/{afd,osv}.py
|  |- conditions.py            the arms, pure functions
|  |- runner.py                cache, interleaving, failure rows
|  |- analysis.py              bootstrap, calibration, figures
|  |- cli.py                   run / analyze entry points
|- data/{items,trials}/        frozen sets, gzipped JSONL
|- figures/
|- tests/
```

Entry points: `jagged run --substrate afd` needs a key; `jagged analyze` needs nothing and
recomputes every published number from committed trials.

**Python**, because the deliverable is statistics. Bootstrap CIs, AUC and calibration curves
are the product, and hand-rolling numerics in TypeScript invites avoidable mistakes. msgspec for the item contract, matching the official SDK's
internals; numpy/scipy for bootstrap; sklearn for AUC and calibration; matplotlib for
figures; uv for the environment.

**The test that matters** is a property test asserting each arm differs from baseline in
exactly the intended field and nothing else. The single-variable claim rests on it, and it's
mechanically checkable rather than checkable by inspection. CI runs it alongside a full
re-analysis of committed trials, so README numbers are machine-verified.

**Data hosting.** Gzipped JSONL in-repo, full raw bundle attached to a GitHub Release.

**Licensing.** Code MIT. AfD text is CC BY-SA 4.0, so derived item sets inherit share-alike;
OSV is CC-BY. `data/` carries its own LICENSE and attribution.

## 10. Shipping

AfD with every arm is a complete study on its own.

## 11. Known limitations

To be carried into the write-up, not buried:

- Two substrates is suggestive of generality, not evidence of it.
- AfD outcomes carry social dynamics alongside policy; mitigated, not eliminated.
- OSV data is clean relative to real-world inputs, so measured degradation is a lower bound.
- Results pin to `jev-1.13` and expire with it.
- Item selection is budget-limited; strata are balanced by design but not exhaustive.

## 12. Open questions

- Is Jev deterministic across identical calls? The jaggedness page says nothing about
  determinism, temperature or variance, so there is no documented answer to check against.
  The repeat arm answers it.
- What are the rate limits and per-call cost? Unknown; measured during the pilot.
- Does the AfD close result parse cleanly at scale, or does it need per-era handling?
- Does 500 items give usable CIs on per-stratum deltas, or does the budget need shifting
  from arms to items?
