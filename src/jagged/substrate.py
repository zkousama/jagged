from typing import Protocol

from jagged.items import Item
from jagged.question import QuestionSpec


class Substrate(Protocol):
    """A labelled corpus. Adapters must never import `jagged.conditions`."""

    name: str

    def load(self, budget: int) -> list[Item]: ...

    def questions(self) -> dict[str, QuestionSpec]: ...
    """Every judgment this substrate supports, keyed as `Item.labels` is.

    Insertion order matters. Question-level arms (`literal`, `indirection`,
    `criteria`) rewrite the first entry, so a substrate lists its primary
    judgment first. State-level arms touch the state and so reach all of them.
    """


REGISTRY: dict[str, Substrate] = {}


def register(substrate: Substrate) -> None:
    REGISTRY[substrate.name] = substrate
