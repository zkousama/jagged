import json

import httpx

from jagged.client import Answer, FakeJev
from jagged.conditions import ARM_NAMES
from jagged.items import Item, Dual
from jagged.question import QuestionSpec
from jagged.runner import Trial, plan_trials, request_hash, run

SPECS = {"verdict": QuestionSpec(
    instructions="Was it deleted?",
    criteria={"true": "Deleted.", "false": "Kept."},
    boundary="A redirect is not a deletion.")}


def _items(n):
    return [Item(id=f"afd:{i}", core={"nomination": f"n{i}"}, context={"sig": "s"},
                 numeric={"participants": Dual(raw="3", banded="a handful")},
                 temporal={"listing_length": Dual(
                     raw="nominated 2024-03-08, closed 2024-03-11",
                     banded="closed three days after it was nominated")},
                 labels={"verdict": i % 2 == 0},
                 stratum="thin_unanimous") for i in range(n)]


def test_request_hash_is_stable_and_order_sensitive():
    a = request_hash({"x": "1", "y": "2"}, SPECS)
    b = request_hash({"x": "1", "y": "2"}, SPECS)
    c = request_hash({"y": "2", "x": "1"}, SPECS)
    assert a == b
    assert a != c, "placebo reorders keys, so hashing must see order"


def test_dropping_the_boundary_changes_the_hash():
    """Baseline and `literal` differ only inside `rendered_criteria`.

    Hashing `criteria` instead would collide them into one cache entry and report
    mode 1 as a flat zero.
    """
    from jagged.conditions import render
    item = _items(1)[0]
    base = request_hash(*render(item, SPECS, "baseline"))
    lit = request_hash(*render(item, SPECS, "literal"))
    assert base != lit, "baseline and literal must not share a cache entry"


def test_plan_covers_the_full_cross_product():
    plan = plan_trials(_items(3), ["baseline", "numbers"], repeats=2, seed=1)
    assert len(plan) == 3 * 2 * 2
    assert len(set(plan)) == len(plan)


def test_plan_interleaves_arms():
    plan = plan_trials(_items(20), ["baseline", "numbers"], repeats=1, seed=1)
    first_half = [arm for _, arm, _ in plan[:20]]
    assert len(set(first_half)) == 2, "arms must not run in blocks"


def test_run_writes_one_row_per_question_with_verbatim_payloads(tmp_path):
    items = _items(2)
    jev = FakeJev([0.1, 0.9, 0.2, 0.8])
    out = run(items, SPECS, ["baseline", "numbers"], repeats=1, client=jev,
              out_path=tmp_path / "t.jsonl", cache=tmp_path / "cache", seed=1, pace=0)
    rows = [json.loads(l) for l in out.read_text().splitlines()]
    assert len(rows) == 4
    assert {r["arm"] for r in rows} == {"baseline", "numbers"}
    assert {r["question"] for r in rows} == {"verdict"}
    assert all(r["request"] and r["response"] for r in rows)
    assert all(r["error"] is None for r in rows)


def test_every_question_gets_its_own_row_from_one_call(tmp_path):
    specs = dict(SPECS)
    specs["window"] = QuestionSpec(instructions="Did it close early?")
    items = [Item(id="afd:0", core={"nomination": "n"}, context={"sig": "s"},
                  numeric={}, temporal={},
                  labels={"verdict": True, "window": False},
                  stratum="thin_unanimous")]
    jev = FakeJev([0.7, 0.2])
    out = run(items, specs, ["baseline"], repeats=1, client=jev,
              out_path=tmp_path / "t.jsonl", cache=tmp_path / "cache", seed=1, pace=0)
    rows = [json.loads(l) for l in out.read_text().splitlines()]
    assert len(rows) == 2
    assert len(jev.requests) == 1, "both questions ride on one call"
    by_q = {r["question"]: r for r in rows}
    assert by_q["verdict"]["probability"] == 0.7
    assert by_q["window"]["probability"] == 0.2
    assert by_q["verdict"]["label"] is True and by_q["window"]["label"] is False
    assert by_q["verdict"]["call_input_tokens"] == 100, "cost is the pilot's open question"


def test_repeats_are_not_collapsed_by_the_cache(tmp_path):
    items = _items(1)
    jev = FakeJev([0.4, 0.6])
    out = run(items, SPECS, ["baseline"], repeats=2, client=jev,
              out_path=tmp_path / "t.jsonl", cache=tmp_path / "cache", seed=1, pace=0)
    probs = [json.loads(l)["probability"] for l in out.read_text().splitlines()]
    assert sorted(probs) == [0.4, 0.6], "each repeat must hit the API separately"


def test_failures_are_recorded_as_rows(tmp_path):
    class Boom:
        def ask(self, state, specs): raise RuntimeError("429 rate limited")
        def close(self): pass
    out = run(_items(1), SPECS, ["baseline"], repeats=1, client=Boom(),
              out_path=tmp_path / "t.jsonl", cache=tmp_path / "cache", seed=1, pace=0)
    row = json.loads(out.read_text().splitlines()[0])
    assert row["probability"] is None
    assert "429" in row["error"]
    assert row["generation_id"] is None


def test_generation_id_comes_off_the_gateway_metadata(tmp_path):
    from jagged.client import Answer

    class OneShot:
        def ask(self, state, specs):
            raw = {"providerMetadata": {"gateway": {"generationId": "gen_abc"}}}
            return {name: Answer(probability=0.5, raw=raw, latency_ms=1,
                                 call_input_tokens=1, call_output_tokens=1)
                    for name in specs}
        def close(self):
            pass

    out = run(_items(1), SPECS, ["baseline"], repeats=1, client=OneShot(),
              out_path=tmp_path / "t.jsonl", cache=tmp_path / "cache", seed=1, pace=0)
    row = json.loads(out.read_text().splitlines()[0])
    assert row["generation_id"] == "gen_abc"


def test_row_records_the_transport_not_an_unused_sdk(tmp_path):
    from importlib.metadata import version
    from jagged.client import EVALUATION_SPEC, GATEWAY_PROTOCOL

    jev = FakeJev([0.4])
    out = run(_items(1), SPECS, ["baseline"], repeats=1, client=jev,
              out_path=tmp_path / "t.jsonl", cache=tmp_path / "cache", seed=1, pace=0)
    row = json.loads(out.read_text().splitlines()[0])
    assert row["httpx_version"] == version("httpx")
    assert row["gateway_protocol"] == GATEWAY_PROTOCOL == "0.0.1"
    assert row["evaluation_spec"] == EVALUATION_SPEC == "4"
    assert "sdk_version" not in row


def _http_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://example.test/eval")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError(
        f"{status} {response.reason_phrase}", request=request, response=response,
    )


class ScriptedStatus:
    """Fake client: a script of HTTP statuses. 200 yields an Answer; anything else raises."""

    def __init__(self, statuses: list[int], probability: float = 0.5):
        self.statuses = list(statuses)
        self.probability = probability
        self.calls = 0

    def ask(self, state, specs):
        self.calls += 1
        status = self.statuses.pop(0)
        if status == 200:
            return {name: Answer(probability=self.probability, raw={"ok": True},
                                 latency_ms=1, call_input_tokens=1,
                                 call_output_tokens=1)
                    for name in specs}
        raise _http_error(status)

    def close(self):
        pass


def test_429_and_503_are_retried(tmp_path):
    for status in (429, 503):
        sleeps = []
        client = ScriptedStatus([status, 200])
        out = run(_items(1), SPECS, ["baseline"], repeats=1, client=client,
                  out_path=tmp_path / f"{status}.jsonl", cache=tmp_path / f"c{status}",
                  seed=1, pace=0, sleeper=sleeps.append)
        row = json.loads(out.read_text().splitlines()[0])
        assert client.calls == 2
        assert row["retries"] == 1
        assert row["error"] is None
        assert row["probability"] == 0.5
        assert sleeps == [4.8]


def test_other_4xx_are_not_retried(tmp_path):
    client = ScriptedStatus([400])
    out = run(_items(1), SPECS, ["baseline"], repeats=1, client=client,
              out_path=tmp_path / "t.jsonl", cache=tmp_path / "cache",
              seed=1, pace=0, sleeper=lambda _: None)
    row = json.loads(out.read_text().splitlines()[0])
    assert client.calls == 1
    assert row["retries"] == 0
    assert row["probability"] is None
    assert "400" in row["error"]


def test_retry_cap_writes_an_error_row(tmp_path):
    client = ScriptedStatus([429, 429, 429, 429])
    out = run(_items(1), SPECS, ["baseline"], repeats=1, client=client,
              out_path=tmp_path / "t.jsonl", cache=tmp_path / "cache",
              seed=1, pace=0, max_retries=3, sleeper=lambda _: None)
    row = json.loads(out.read_text().splitlines()[0])
    assert client.calls == 4
    assert row["retries"] == 3
    assert row["probability"] is None
    assert "429" in row["error"]


def test_calls_are_paced(tmp_path):
    clock = {"t": 0.0}
    sleeps = []

    def now():
        return clock["t"]

    def sleeper(seconds):
        sleeps.append(seconds)
        clock["t"] += seconds

    client = ScriptedStatus([200, 200])
    run(_items(2), SPECS, ["baseline"], repeats=1, client=client,
        out_path=tmp_path / "t.jsonl", cache=tmp_path / "cache",
        seed=1, pace=2.4, sleeper=sleeper, clock=now)
    assert client.calls == 2
    assert sleeps == [2.4]
