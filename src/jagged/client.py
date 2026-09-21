import os
import time

from msgspec import Struct

from jagged.question import QuestionSpec

# httpx defaults to five seconds. The context arms deliberately send the largest
# states in the study, so that default would time them out more than any other
# arm and the run would read our own impatience as the cost of padding.
REQUEST_TIMEOUT = 120.0
GATEWAY_URL = "https://ai-gateway.vercel.sh/v4/ai/evaluation-model"
GATEWAY_MODEL = "typesafe-ai/jev"


class Answer(Struct, frozen=True):
    probability: float
    raw: dict
    latency_ms: int
    call_input_tokens: int | None = None
    call_output_tokens: int | None = None


class JevClient:
    """One call site. httpx against the Vercel AI Gateway; responses stored verbatim."""

    def __init__(self, model: str = "jev-1.13", timeout: float = REQUEST_TIMEOUT,
                 http=None, api_key: str | None = None):
        self.model = model
        self.timeout = timeout
        self.api_key = api_key if api_key is not None else os.environ["AI_GATEWAY_API_KEY"]
        if http is None:
            import httpx
            http = httpx.Client(timeout=timeout)
        self._http = http

    def ask(self, state: dict, specs: dict[str, QuestionSpec]) -> dict[str, Answer]:
        """Every question for an item goes in one call, as the docs' own example does.

        The 64k budget covers all state and questions together, so two nouls over
        one state costs far less than two calls and keeps the pair on identical
        state by construction.
        """
        body = {
            "state": state,
            "questions": {name: spec.to_noul() for name, spec in specs.items()},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "ai-gateway-protocol-version": "0.0.1",
            "ai-evaluation-model-specification-version": "4",
            "ai-model-id": GATEWAY_MODEL,
        }
        started = time.perf_counter()
        response = self._http.post(
            GATEWAY_URL, headers=headers, json=body, timeout=self.timeout,
        )
        elapsed = int((time.perf_counter() - started) * 1000)
        response.raise_for_status()
        raw = response.json()
        usage = raw.get("usage") or {}
        answers = raw.get("answers") or {}
        # Usage is billed per call, and a call carries every question. The column
        # names say so: summing them across rows double-counts. Token fields are
        # camelCase on the gateway; generationId stays in raw for the trial row.
        return {name: Answer(probability=float(answers[name]["probability"]),
                             raw=raw, latency_ms=elapsed,
                             call_input_tokens=usage.get("inputTokens"),
                             call_output_tokens=usage.get("outputTokens"))
                for name in specs}

    def close(self) -> None:
        close = getattr(self._http, "close", None)
        if close:
            close()


class FakeJev:
    def __init__(self, script: list[float]):
        self.script = list(script)
        self.requests: list[tuple[dict, dict[str, QuestionSpec]]] = []

    def ask(self, state: dict, specs: dict[str, QuestionSpec]) -> dict[str, Answer]:
        self.requests.append((state, specs))
        out = {}
        for name in specs:
            assert self.script, "FakeJev ran out of scripted responses"
            out[name] = Answer(probability=self.script.pop(0), raw={"fake": True},
                               latency_ms=1, call_input_tokens=100,
                               call_output_tokens=2)
        return out

    def close(self) -> None:
        pass
