# Pilot manifest

Declared pilot, per PREREGISTRATION.md. Its job is to set what could not be known in
advance: cost, whether two-decimal probabilities give usable intervals, whether repeats
agree, and whether the two scored strata fill.

- AfD log date: 2024 February 6 (the main run excludes this date)
- Items: first 50 usable of 56 on that date
- Arms: 11, repeats: 3, calls: 1,650
- Transport: Vercel AI Gateway, `typesafe-ai/jev`

## Before the run

- Gateway credits: balance 5, used 0
- Gateway catalogue: 376 models, one TypeSafe entry, `typesafe-ai/jev`
- Models page (archived as `models-page-before.html`): the only version strings are
  `jev-1.13` and `jev-1.13.0`
- Strata available on the date: 36 `thin_unanimous`, 20 `well_attended`, 0 `contested`
  (contested closes are dropped by the labelling rule, as registered)

## Attempt 1 — rate limited

The run completed with exit 0 and wrote 3,300 rows. 3,038 were errors: 3,030
`429 Too Many Requests` and 8 `503 Service Unavailable`. Only 131 of 1,650 calls
succeeded. The first error came at row 60, and successes kept arriving intermittently
after it, so the gateway applies a sustained-rate limit rather than a hard cap. The
runner is sequential with no pacing or retry, so it ran straight into it.

Kept as `attempt-1.jsonl` for the record. It is not the pilot's data.

What the 131 successful calls still establish:

- **Cost.** $0.0124 market cost for 131 calls, about $0.000095 each. The full pilot is
  roughly $0.16 and the 16,500-call main run roughly $1.60. Both fit the credit; the
  gateway billed $0 during the free window.
- **Latency.** Median 384 ms, p95 545 ms.
- **Repeats.** 16 of 28 repeat groups returned identical probabilities. Every one that
  differed was off by 0.01 or 0.02, one or two rounding steps. Jev is effectively
  deterministic below the rounding precision, and that puts the repeat noise floor at
  roughly 0.01 to 0.02 in probability.
- **Precision.** 67 distinct probability values of 101 possible, 2.3% at the extremes.
  The values spread rather than piling at 0 and 1, which is better for AUC than feared.
- **Strata.** Both scored strata fill on this date, as recorded above.
- **Version.** The models page read after the run still carried only `jev-1.13` and
  `jev-1.13.0` (archived as `models-page-after.html`). The run did not straddle a release.

Still open: whether two-decimal probabilities give usable per-stratum intervals. The
successful calls are 5 to 18 per arm, with 6 for baseline, too thin for paired deltas.
That needs a complete run.
