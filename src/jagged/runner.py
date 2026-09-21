import hashlib
import json
import random
import subprocess
import time
from pathlib import Path

import msgspec
from msgspec import Struct

from jagged.client import EVALUATION_SPEC, GATEWAY_PROTOCOL
from jagged.conditions import render
from jagged.items import Item
from jagged.question import QuestionSpec


class Trial(Struct):
    trial_id: str
    substrate: str
    item_id: str
    stratum: str
    arm: str
    repeat: int
    question: str
    request_hash: str
    request: dict
    response: dict | None
    probability: float | None
    label: bool
    latency_ms: int | None
    call_input_tokens: int | None
    call_output_tokens: int | None
    generation_id: str | None
    error: str | None
    retries: int
    model: str
    httpx_version: str
    gateway_protocol: str
    evaluation_spec: str
    run_id: str
    git_commit: str
    ts: float


PACE_INTERVAL = 2.4
MAX_RETRIES = 5
RETRYABLE = frozenset({429, 503})


def backoff_seconds(attempt: int) -> float:
    return PACE_INTERVAL * (2 ** attempt)


def _status_code(exc: BaseException) -> int | None:
    response = getattr(exc, "response", None)
    return getattr(response, "status_code", None)


def request_hash(state: dict, specs: dict[str, QuestionSpec]) -> str:
    """Hash what actually goes over the wire.

    `rendered_criteria`, not `criteria`: the boundary only merges in at render
    time, so hashing the raw field makes baseline and `literal` collide, share a
    cache entry and report a zero delta for mode 1 with nothing looking wrong.
    """
    payload = json.dumps(
        {"state": list(state.items()),
         "questions": [[name, spec.instructions, spec.rendered_criteria]
                       for name, spec in specs.items()]},
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def plan_trials(items: list[Item], arms: list[str], repeats: int, seed: int):
    plan = [(i.id, arm, r) for i in items for arm in arms for r in range(repeats)]
    random.Random(seed).shuffle(plan)
    return plan


def _httpx_version() -> str:
    from importlib.metadata import PackageNotFoundError, version
    try:
        return version("httpx")
    except PackageNotFoundError:
        return "unknown"


def _generation_id(raw: dict | None) -> str | None:
    if not raw:
        return None
    gateway = (raw.get("providerMetadata") or {}).get("gateway") or {}
    return gateway.get("generationId")


def _git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def run(items, specs, arms, repeats, client, out_path: Path, cache: Path,
        seed: int = 1, model: str = "jev-1.13", substrate: str = "afd",
        pace: float = PACE_INTERVAL, max_retries: int = MAX_RETRIES,
        sleeper=time.sleep, clock=time.monotonic) -> Path:
    out_path, cache = Path(out_path), Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    by_id = {i.id: i for i in items}
    run_id = f"{int(time.time())}-{seed}"
    commit = _git_commit()
    last_request = None

    with out_path.open("w", encoding="utf-8") as fh:
        for item_id, arm, repeat in plan_trials(items, arms, repeats, seed):
            item = by_id[item_id]
            state, rendered = render(item, specs, arm)
            rhash = request_hash(state, rendered)
            # repeat index in the key: identical requests must still hit the API
            cache_file = cache / f"{rhash}-{repeat}.json"

            answers, error, retries = {}, None, 0
            if cache_file.exists():
                answers = json.loads(cache_file.read_text())["answers"]
            else:
                while True:
                    if last_request is not None and pace > 0:
                        wait = pace - (clock() - last_request)
                        if wait > 0:
                            sleeper(wait)
                    last_request = clock()
                    try:
                        got = client.ask(state, rendered)
                        answers = {n: {"p": a.probability, "r": a.raw, "ms": a.latency_ms,
                                       "in": a.call_input_tokens,
                                       "out": a.call_output_tokens}
                                   for n, a in got.items()}
                        cache_file.write_text(json.dumps({"answers": answers}))
                        error = None
                        break
                    except Exception as exc:
                        status = _status_code(exc)
                        if status in RETRYABLE and retries < max_retries:
                            retries += 1
                            sleeper(backoff_seconds(retries))
                            continue
                        error = f"{type(exc).__name__}: {exc}"
                        break

            # One call, one row per question. A failed call writes a row per
            # question too, so completion rate stays comparable across arms.
            for name, spec in rendered.items():
                blob = answers.get(name)
                trial = Trial(
                    trial_id=f"{item.id}|{arm}|{repeat}|{name}",
                    substrate=substrate, item_id=item.id, stratum=item.stratum,
                    arm=arm, repeat=repeat, question=name, request_hash=rhash,
                    request={"state": state, "instructions": spec.instructions,
                             "criteria": spec.rendered_criteria},
                    response=blob["r"] if blob else None,
                    probability=blob["p"] if blob else None,
                    label=item.labels[name],
                    latency_ms=blob["ms"] if blob else None,
                    call_input_tokens=blob.get("in") if blob else None,
                    call_output_tokens=blob.get("out") if blob else None,
                    generation_id=_generation_id(blob.get("r") if blob else None),
                    error=error, retries=retries, model=model,
                    httpx_version=_httpx_version(),
                    gateway_protocol=GATEWAY_PROTOCOL,
                    evaluation_spec=EVALUATION_SPEC,
                    run_id=run_id, git_commit=commit, ts=time.time(),
                )
                fh.write(msgspec.json.encode(trial).decode() + "\n")
    return out_path
