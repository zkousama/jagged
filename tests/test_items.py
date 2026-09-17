import pytest
from jagged.items import Dual, Item, validate_item


def _item(**over):
    base = dict(
        id="afd:Example",
        core={"nomination": "Fails WP:GNG."},
        context={"signature": "~~~~"},
        numeric={"participants": Dual(raw="7", banded="a handful of editors")},
        temporal={"listing_length": Dual(raw="nominated 2024-03-03, closed 2024-03-05",
                                        banded="closed two days after it was nominated")},
        labels={"verdict": True, "window": True},
        stratum="contested",
    )
    base.update(over)
    return Item(**base)


def test_item_round_trips_through_msgspec():
    import msgspec
    item = _item()
    assert msgspec.json.decode(msgspec.json.encode(item), type=Item) == item


def test_core_and_context_keys_must_be_disjoint():
    bad = _item(core={"shared": "a"}, context={"shared": "b"})
    with pytest.raises(ValueError, match="overlap"):
        validate_item(bad)


def test_stratum_must_be_non_empty():
    with pytest.raises(ValueError, match="stratum"):
        validate_item(_item(stratum=""))


def test_an_item_without_labels_is_rejected():
    with pytest.raises(ValueError, match="labels"):
        validate_item(_item(labels={}))


def test_valid_item_passes():
    validate_item(_item())
