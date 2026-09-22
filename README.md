# jagged

Measures the failure modes TypeSafe documents for `jev-1.13`. Baseline is
the configuration the jaggedness page recommends. Each arm breaks one
piece of that advice. The first substrate is Wikipedia Articles for
Deletion.

No data has been collected.

## Setup

Python 3.12 or newer. [`uv`](https://docs.astral.sh/uv/) is the
environment.

```sh
uv sync
```

A live run talks to Vercel's AI Gateway. Put `AI_GATEWAY_API_KEY` in
`.env`.

## Run

```sh
uv run jagged run --items 500 --repeats 3 --out data/trials/afd.jsonl
uv run jagged analyze
```

`jagged run` needs the key. `jagged analyze` does not: it reads committed
trial records and reprints the deltas. Until those records exist there
is nothing to analyse.

```sh
uv run pytest
```

The pre-registered conditions, metrics, strata, noise floors and
decision rule are in [`PREREGISTRATION.md`](PREREGISTRATION.md).

## Licence

Code is MIT. AfD text and the item sets derived from it are CC BY-SA
4.0; see [`data/LICENSE`](data/LICENSE).
