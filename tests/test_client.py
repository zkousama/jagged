import pytest
from jagged.client import REQUEST_TIMEOUT, Answer, FakeJev, JevClient
from jagged.question import QuestionSpec

SPECS = {"verdict": QuestionSpec(instructions="Was it deleted?"),
         "window": QuestionSpec(instructions="Did it close early?")}

GATEWAY = {
    "answers": {
        "verdict": {"probability": 0.81},
        "window": {"probability": 0.12},
    },
    "rounding": {"probabilityDecimals": 2},
    "usage": {"inputTokens": 40, "outputTokens": 6},
    "providerMetadata": {"gateway": {"generationId": "gen_abc", "marketCost": 0.001}},
}


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class Recorder:
    def __init__(self, payload=GATEWAY):
        self.payload = payload
        self.kwargs = None

    def post(self, url, **kwargs):
        self.url = url
        self.kwargs = kwargs
        return FakeResponse(self.payload)

    def close(self):
        pass


def test_fake_returns_one_scripted_answer_per_question():
    jev = FakeJev([0.82, 0.11])
    got = jev.ask({"nomination": "x"}, SPECS)
    assert set(got) == {"verdict", "window"}
    assert all(isinstance(a, Answer) for a in got.values())
    assert got["verdict"].probability == 0.82
    assert got["window"].probability == 0.11


def test_fake_records_the_request_it_was_given():
    jev = FakeJev([0.1, 0.2])
    jev.ask({"nomination": "x"}, SPECS)
    assert jev.requests == [({"nomination": "x"}, SPECS)]


def test_running_out_of_script_is_an_error_not_a_silent_default():
    jev = FakeJev([0.5])
    with pytest.raises(AssertionError):
        jev.ask({"a": "b"}, SPECS)


def test_the_client_sends_an_explicit_timeout():
    """The padding arms send the biggest states; an unset timeout would cut them off.

    A timeout that fires more often on `context_100` than on `baseline` shows up
    as a completion-rate gap and reads exactly like the effect under test.
    """
    class Boom(Recorder):
        def post(self, url, **kwargs):
            self.url = url
            self.kwargs = kwargs
            raise RuntimeError("far enough")

    rec = Boom()
    client = JevClient(http=rec, api_key="k")
    with pytest.raises(RuntimeError):
        client.ask({"a": "b"}, SPECS)
    assert rec.kwargs["timeout"] == REQUEST_TIMEOUT


def test_usage_is_carried_off_the_call():
    got = FakeJev([0.3, 0.4]).ask({"a": "b"}, SPECS)
    assert got["verdict"].call_input_tokens == 100
    assert got["window"].call_output_tokens == 2


def test_client_posts_the_gateway_payload_and_reads_the_response():
    rec = Recorder()
    client = JevClient(http=rec, api_key="k")
    got = client.ask({"nomination": "x"}, SPECS)
    assert rec.url == "https://ai-gateway.vercel.sh/v4/ai/evaluation-model"
    assert rec.kwargs["headers"] == {
        "Authorization": "Bearer k",
        "Content-Type": "application/json",
        "ai-gateway-protocol-version": "0.0.1",
        "ai-evaluation-model-specification-version": "4",
        "ai-model-id": "typesafe-ai/jev",
    }
    assert rec.kwargs["timeout"] == REQUEST_TIMEOUT
    assert rec.kwargs["json"] == {
        "state": {"nomination": "x"},
        "questions": {
            "verdict": {"type": "boolean", "instructions": "Was it deleted?"},
            "window": {"type": "boolean", "instructions": "Did it close early?"},
        },
    }
    assert got["verdict"].probability == 0.81
    assert got["window"].probability == 0.12
    assert got["verdict"].call_input_tokens == 40
    assert got["verdict"].call_output_tokens == 6
    assert got["verdict"].raw["providerMetadata"]["gateway"]["generationId"] == "gen_abc"
    assert got["verdict"].raw["rounding"]["probabilityDecimals"] == 2
