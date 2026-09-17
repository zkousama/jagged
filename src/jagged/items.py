from msgspec import Struct


class Dual(Struct, frozen=True):
    """A value in both the forms the study needs.

    `raw` is what a naive integration sends: a number, or an ISO date. `banded`
    is the semantic phrasing the docs recommend. Modes 2 and 3 swap one for the
    other over identical items, which only works if the baseline already carries
    the banded form. A field present in one arm and absent in the other would be
    testing presence, not representation.
    """

    raw: str
    banded: str


class Item(Struct, frozen=True):
    """One labelled case.

    `labels` is keyed by question name, because a substrate can carry more than
    one judgment over the same state. AfD carries two: the deletion verdict, and
    whether the discussion closed before the seven-day listing period elapsed.
    The second exists so mode 3 has a judgment that actually needs the dates —
    swapping a date's representation proves nothing if nothing reads it.
    """

    id: str
    core: dict[str, str]
    context: dict[str, str]
    numeric: dict[str, Dual]
    temporal: dict[str, Dual]
    labels: dict[str, bool]
    stratum: str


def validate_item(item: Item) -> None:
    overlap = set(item.core) & set(item.context)
    if overlap:
        raise ValueError(f"core/context key overlap: {sorted(overlap)}")
    if not item.stratum:
        raise ValueError("stratum must be non-empty")
    if not item.id:
        raise ValueError("id must be non-empty")
    if not item.labels:
        raise ValueError("labels must be non-empty")
