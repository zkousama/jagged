# Measuring jev-1.13's documented failure modes

Design spec. 2026-09-17.

## 1. The question

TypeSafe publishes a page listing nine ways jev-1.13 degrades, and for each one it
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

In: seven of the nine documented modes, one substrate, one model version.

Out:
- **Generation** (mode 9). Jev isn't trained to generate and the docs say so. Testing it
  would be theatre. Stated in the write-up rather than faked.
- **Common-sense structural invariants** (mode 8), as an arm. It doesn't fit the
  one-variable-per-arm frame: the
  page's claim is that separate questions don't stand in arithmetic relation to each
  other, so there is no baseline to degrade from. It is also the cheapest of the nine to
  measure — ask a judgment and its negation as separate Nouls, sum the probabilities,
  report the distance from 1. The page's own example sums to 1.19. That belongs in the
  write-up as a measured aside rather than a twelfth arm, and §5 records where it puts two
  existing arms at risk.
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
    labels: dict[str, bool]     # ground truth, one per question
    stratum: str                # difficulty band
```

Temporal fields carry **both** forms for the same reason numeric ones do. An earlier
draft typed them as a bare ISO string, which made the baseline omit dates entirely and
turned mode 3 into a test of whether adding a field hurts rather than whether its
representation matters. A manipulation that changes presence is not a manipulation of
representation.

`banded` is load-bearing. It's what lets the same question be asked numerically and
semantically over identical items, which is the whole of mode 2.

`labels` is a dict because one state can carry more than one judgment, and mode 3 needs
that. A date manipulation only measures date handling if some judgment reads the date, and
"was this article deleted" doesn't. So AfD carries a second question — did the discussion
close before the seven-day listing period elapsed — whose ground truth is the two
timestamps and nothing else. Both questions ride on a single call, since the documented
budget covers all state and questions together.

The banded form of a temporal field has to stop short of the answer. "Closed within a week"
would settle the window question outright and hand mode 3 an effect size that was really a
giveaway; "closed three days after it was nominated" is the arithmetic done in code, which
is what the docs actually prescribe, and still leaves the model something to weigh.

```python
class Substrate(Protocol):
    name: str
    def load(self, budget: int) -> list[Item]: ...
    def questions(self) -> dict[str, Question]: ...  # baseline Nouls, un-manipulated
```

Two constraints belong in the interface rather than in discipline:

- **Adapters never see the conditions.** They can't tailor items to flatter a manipulation.
- **Question order is the substrate's.** Question-level arms reword the first entry, since
  there is no generic way to reword an arbitrary question. State-level arms reach all of
  them by construction.
- **`stratum` is assigned by a rule fixed before any model call.** Difficulty cannot be
  redefined after seeing results.

## 4. Substrates

### 4.1 Wikipedia Articles for Deletion (v1)

Every AfD is a public page under `Wikipedia:Articles for deletion/<title>` in namespace 4,
carrying the full argument thread and an administrator's closing decision. The archive runs
about twenty years deep. Closed discussions are wrapped in a `xfd-closed` boilerplate block.

The task is applying a written rule corpus (WP:N, WP:GNG, WP:NOT) to a messy human
argument, which puts **literal reading** — instruction-following, not arithmetic — at the
centre. That's the most interesting of the nine modes and the one every Jev integration is
implicitly betting on.

- `core`: the discussion with bolded votes and vote-only lines stripped. The
  nomination sits in that thread; it is not a separate field.
- `context`: boilerplate, signatures, thread furniture, procedural chatter,
  with the same vote strip, so padding cannot restore the tally
- `numeric`: participation counts, source counts. The participant count is
  taken from the unstripped body.
- `temporal`: the listing length, as two ISO dates or as the gap in words
- `labels`: `verdict`, the closing decision (see the labelling choice below); and
  `window`, whether the close came before the seven-day listing period elapsed
- `stratum`: participation volume and disagreement, banded

**Ceiling, and why core is the stripped discussion.** Attempt 2 of the declared
pilot (`data/pilot/manifest.md`) put the whole discussion in `core`, votes
included. Baseline verdict AUC was 0.997 at 98% accuracy: the task was a tally.
Moving the thread into `context` would hand those votes to the padding arms.
The votes have to leave every field.

The 50-item design-B check on the same date (same manifest) left the arguments
in `core` and stripped the votes. Baseline accuracy was 0.940 and ECE 0.234;
adversarial moved accuracy by −0.580 and ECE by +0.353, both clearing the
placebo band. Ranking stayed at the ceiling, because the remaining arguments
still determine the close. Accuracy at 0.5 and ECE are therefore the primaries
on this substrate; AUC is computed and reported, and is not in the family the
decision rule corrects.

**Confound, and the labelling choice.** AfD outcomes partly reflect who showed up, not only
the merits, so raw outcome prediction is partly social-dynamics prediction. Two candidate
labellings address this, and exactly one is frozen at pre-registration:

- **Verdict, restricted.** The closing decision, on unanimous closes only. Simpler to parse,
  and unanimity strips most of the social variance.
- **Policy basis.** Whether the policy the closing admin cited actually applies. Closer to
  the judgment being tested, and harder to extract reliably.

Verdict-restricted is the default unless the pilot shows unanimous closes are too scarce or
too easy to stratify usefully. The write-up states the confound either way.

A discussion without two parseable timestamps is dropped rather than half-labelled. An item
that could answer one question and not the other would put mode 3 on a different item set
from every other arm, which is worse than a smaller corpus.

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
- `labels`: `affected`, computed from the published range
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
| 3 | Date and time comparison | Relative phrasing replaced with raw ISO dates, read on `window` |
| 4 | Indirection | Semantically equivalent double negative |
| 5 | Large state full of irrelevant detail | `core` + 25% / 50% / 100% of `context` |
| 6 | Adversarial content | Directive injected into a `context` field |
| 7 | Contradictory instructions and criteria | Criteria polarity inverted against instructions |
| P | Placebo | State field order shuffled |

Numbers and names in that table are the page's own, in the page's order. The study sets aside
one piece of TypeSafe's advice at a time, so the mapping to their list has to be checkable at
a glance.

Mode 5 is a dose-response rather than on/off, because three points make a curve.

**Each arm is read on the question its manipulation reaches.** Mode 3 on `window`, which is
the only judgment here that consults a date; everything else on `verdict`. Every arm is
reported on both, and which one the decision rule counts is pre-registered rather than
chosen once the deltas are in.

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
mitigation. It's the weakest of the nine, and this is the one arm measuring a failure its
own documentation has no answer for.

**Mode 8 puts two of these arms at risk, and the write-up says so.** The page states that
"P(noul) and 1 - P(not noul) may not be directly comparable", with its own example summing
to 1.19. The criteria arm inverts true/false polarity and the indirection arm routes the
question through a double negative; both assume a complement behaves like a complement.
Whatever they measure is the contradiction or indirection effect *plus* whatever structural
non-invariance the model already carries. The invariance probe above is what separates them:
run it on the same items, and its deviation from 1 is the floor those two arms have to clear,
exactly as the placebo is the floor for the rest.

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

429 and 503 are a different class. The gateway applies a sustained-rate limit (about 25
successful calls a minute in the first pilot attempt), and those errors land on whichever
arm comes next in the shuffled order, so they are infrastructure noise. They are retried
with exponential backoff up to five times, and the row records how many retries it took.
Other 4xx are never retried: a 400 from an oversized state is arm-dependent, `context_100`
is the arm most likely to hit it, and that failure is part of the measurement. A call that
exhausts the retry cap is still a row. Nothing is retried into silence.

Calls are paced at 2.4 seconds (25 per minute) so most 429s never happen. Cached hits skip
the wait; an interrupted run resumes.

The limit is "64k tokens together for all `state` and `questions`; 32k tokens for the `state` +
the longest `question`". It is not a ceiling on state alone, so the cap has to be computed
against state plus the rendered question or the padding arm will fail at a threshold the
adapter thinks it's below.

**Trial record** — the publishable artifact:

```
trial_id, substrate, item_id, stratum, arm, repeat, question,
request_hash, request (verbatim), response (verbatim),
probability, label, latency_ms, call_input_tokens, call_output_tokens,
generation_id, error, retries, model, httpx_version, gateway_protocol, evaluation_spec,
run_id, git_commit, ts
```

Verbatim request and response are what make "recompute my numbers without an API key" true.

`call_*` rather than plain `input_tokens`: usage is billed per call, and one call carries
every question asked against that state. The prefix is there so nobody sums the column
across rows and doubles the bill. `generation_id` is Vercel's `providerMetadata.gateway.generationId`,
the handle into their log for the same call.

`httpx_version`, `gateway_protocol` and `evaluation_spec` replace `sdk_version`. The
client is httpx against the gateway, so the row records the httpx version that made
the request and the two header values that defined the wire (`ai-gateway-protocol-version`
0.0.1, `ai-evaluation-model-specification-version` 4). A typesafe-sdk version would name
a library that never saw the call.

**Set the timeout explicitly.** The client is httpx, which times out at five seconds unless
you pass one. The padding arms send the largest states in the study by construction, so
that default would cut them off more often than any other arm, and a completion-rate gap
that tracks state size is indistinguishable from the effect mode 5 is trying to measure.
An unset default would have manufactured the result.

**Run manifest** pins model version, httpx version, gateway protocol, evaluation spec,
selection seed and git commit. The jaggedness page is versioned at `jev-1.13`; these
results expire with it.

**The transport is Vercel's AI Gateway, over plain HTTP.** There is no TypeSafe key in this
environment, and the Python SDK will not start without one. The client is httpx against
`POST https://ai-gateway.vercel.sh/v4/ai/evaluation-model`, with
`ai-gateway-protocol-version: 0.0.1`, `ai-evaluation-model-specification-version: 4` and
`ai-model-id: typesafe-ai/jev`. A question on the wire is
`{"type": "boolean", "instructions": ..., "criteria": {"true": ..., "false": ...}}`.
`QuestionSpec.to_noul()` builds that dict.

The payload still cannot name a Jev version. The gateway lists 376 models and exactly one
TypeSafe entry, `typesafe-ai/jev`. Every versioned form of that id returns `Model not found`,
and the response names no version either: 65 leaves of the result object carry
`typesafe-ai/jev` or `typesafe-ai` and nothing more.

How much that costs depends on how many versions exist, and right now the answer is one.
TypeSafe's models page lists `jev-1.13.0` as the only concrete version, with `jev-latest`
and `jev-preview` both pointing at it and no preview build available. So a gateway run
completed today is attributable by elimination rather than by record. The run manifest
captures the models page as read before and after the run, and a run that straddles a
version change is discarded. That is weaker than a version in the payload and strong
enough to proceed on. Cloudflare's own model page
documents a response carrying `"model": "jev-1.13.0"` — documented rather than measured
here, and enough to record what answered even when the request can't pin it. The TypeSafe
API takes a versioned id directly. OpenRouter carries no Jev entry at all; its public
catalogue listed 446 models on 2026-09-20 and none of them was TypeSafe's.

The response body carries `answers.<name>.probability`, `rounding.probabilityDecimals`,
`usage.inputTokens` and `usage.outputTokens`, and `providerMetadata.gateway.generationId`
plus `marketCost`. Token fields are camelCase on the wire; the trial row keeps the
`call_*` names. The generation id is stored next to them.

**Two decimals is the model, not the route.** Probabilities come back rounded to two places
and `rounding.probabilityDecimals` declares it, which leaves 101 distinct values and costs
AUC resolution through ties. That is TypeSafe's behaviour rather than a gateway limitation:
the AI SDK's TypeSafe provider defines no provider options at all, and any unknown key under
`providerOptions.typesafe` returns the same `unsupported` warning — `probabilityDecimals`
and `bananaDecimals` are indistinguishable to it. Nothing in the documented surface asks for
more precision, so the pilot has to establish whether two decimals give usable intervals
rather than assume a knob exists.

**Pin the page, not just the model.** The page carries its own stamp — "Applies to
`jev-1.13`. Last reviewed 2026-09-17" — and no changelog. The control condition is that
page's advice, so the run manifest records that line verbatim alongside the model id, and
the run archives the page as read. A review date that moves while the model id holds still
would otherwise change the baseline with nothing in the results to show it.

**Budget.** Roughly 500 items x 11 arms x 3 repeats ~ 16k calls per substrate. Pinned as
config. Jev is early access with no public pricing, so cost is an unknown to measure during
the pilot rather than estimate now — though the response carries `inputTokens` and
`outputTokens`, so the pilot measures consumption exactly and only the price stays
unknown.

## 7. Analysis

**Estimand: paired delta against baseline.** Bootstrap over items — resample with
replacement, recompute the metric in both arms on the resampled set, take the difference.
Repeats average within item first.

**Metrics per arm and question:**
- Accuracy at 0.5 and ECE, co-primary. The documented cut, and the calibration
  of the only number Jev returns. The decision rule and Benjamini-Hochberg
  correction at q=0.05 run across the full family of non-baseline arms × both
  primaries. The placebo band is metric-specific: an accuracy delta is judged
  against the placebo accuracy interval, an ECE delta against the placebo ECE
  interval.
- AUC, computed and reported, not in that family. Attempt 2 of the declared
  pilot (`data/pilot/manifest.md`) sat at verdict AUC 0.997 with the votes in
  the state; the 50-item design-B check on the same date stayed at the ranking
  ceiling after they left, because the discussion still determines the close.

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
clears the placebo band on that metric, it survives Benjamini-Hochberg at q=0.05 across the
family of arms × both primaries, and its direction holds across repeats. Everything else
is reported as null.

**Nulls get equal billing.** If padding costs nothing measurable, that piece of advice doesn't
change the answer on this task, and the write-up reports it. Pre-committing to publish nulls
is what makes the positive findings believable.

**The headline is an interaction.** Per-stratum deltas with their own intervals. "Padding
costs nothing on easy items and eighteen points on hard ones" is a difference-of-differences
and needs its own CI. Pooled averages erase the unevenness the jaggedness page claims.

**Figures:**
1. dAccuracy by stratum, one line per mode — the degradation curves
2. Reliability diagram, baseline against worst arm — the calibration result
3. Dose-response for context padding at 25/50/100%
4. Forest plot of every primary delta (accuracy and ECE) with CIs and the
   metric-specific placebo band drawn in

Latency comes free and is worth reporting; speed is Jev's pitch and nobody has measured
what padding costs in milliseconds. Token consumption comes free the same way, off the
response's own usage block, and on the dose-response arms it is the more useful of the two:
it is what padding actually costs to run.

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
|  |- substrates/afd.py
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

**Licensing.** Code MIT. AfD text is CC BY-SA 4.0, so derived item sets inherit share-alike.
`data/` carries its own LICENSE and attribution.

## 10. Shipping

AfD with every arm is a complete study on its own.

## 11. Known limitations

To be carried into the write-up, not buried:

- One substrate. The results describe Jev on Wikipedia deletion discussions, and §4.2's
  OSV design is the replication that would test them on another task.
- AfD outcomes carry social dynamics alongside policy; mitigated, not eliminated.
- Results pin to `jev-1.13` and to the jaggedness page at its stated review date, captured
  in the run manifest.
- Modes 8 and 9 are measured or excluded rather than run as arms, so the one-piece-at-a-time
  design covers seven of nine, and the write-up says which.
- Item selection is budget-limited; strata are balanced by design but not exhaustive.

## 12. Open questions

- Is Jev deterministic across identical calls? The jaggedness page says nothing about
  determinism, temperature or variance, so there is no documented answer to check against.
  The repeat arm answers it.
- What are the rate limits and the price per token? The SDK reports token counts per call,
  so consumption is measured rather than guessed; the rate limits and the price are not
  published and the pilot has to find them.
- Does the AfD close result parse cleanly at scale, or does it need per-era handling?
- Does 500 items give usable CIs on per-stratum deltas, or does the budget need shifting
  from arms to items?
