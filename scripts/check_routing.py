"""Tally where the gateway says every saved call went.

Each response the AI Gateway returns carries its own routing record under
providerMetadata.gateway.routing: the provider it resolved to, every attempt it
made, and the fallbacks it had available. This reads that record from every saved
response and counts the distinct routes, so a run that fell back to another
provider, or took more than one attempt, would show up as a second line.

    uv run python scripts/check_routing.py

No key needed: it reads the committed trial files.
"""

import collections
import gzip
import json

FILES = [
    "data/trials/afd.jsonl.gz",
    "data/followup/invariance.jsonl.gz",
    "data/followup/decompose.jsonl.gz",
]


def route(response: dict) -> tuple:
    routing = response.get("providerMetadata", {}).get("gateway", {}).get("routing", {})
    attempts = routing.get("modelAttempts") or []
    provider_attempts = [p for a in attempts for p in a.get("providerAttempts", [])]
    return (
        routing.get("originalModelId"),
        routing.get("finalProvider"),
        len(attempts),
        len(provider_attempts),
        tuple(sorted({p.get("provider") for p in provider_attempts})),
        tuple(routing.get("fallbacksAvailable") or []),
        all(p.get("success") for p in provider_attempts),
    )


def main() -> None:
    total = collections.Counter()
    for path in FILES:
        routes, errored = collections.Counter(), 0
        for line in gzip.open(path, "rt", encoding="utf-8"):
            row = json.loads(line)
            if not row.get("response"):
                errored += 1
                continue
            routes[route(row["response"])] += 1
        total.update(routes)
        print(f"{path}: {sum(routes.values())} responses, {errored} errored rows")
        for r, n in routes.most_common():
            model, provider, attempts, tries, providers, fallbacks, ok = r
            print(f"  {n:6}  {model} -> {provider}, {attempts} model attempt(s), "
                  f"{tries} provider attempt(s) via {', '.join(providers)}, "
                  f"fallbacks available: {', '.join(fallbacks) or 'none'}, all succeeded: {ok}")
    print(f"{sum(total.values())} responses, {len(total)} distinct route(s)")


if __name__ == "__main__":
    main()
