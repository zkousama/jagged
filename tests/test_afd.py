from jagged.items import validate_item
from jagged.substrates.afd import AfdSubstrate, band_participants, stratum_for
from jagged.substrates.afd_parse import Close

DISCUSSION = """{{Afd top/old}}  The result was '''delete'''‎__EXPECTED_UNCONNECTED_PAGE__. Fails [[WP:GNG]].
===[[:Example Article]]===
:{{la|1=Example Article}}
Nominating. No independent sources found. [[User:A|A]] 10:00, 1 March 2024 (UTC)
*'''Delete''' agree with nom. [[User:B|B]] 11:00, 1 March 2024 (UTC)
*'''Delete''' nothing in the usual databases. [[User:C|C]] 12:00, 1 March 2024 (UTC)
*'''Delete''' searched, no coverage. [[User:D|D]] 13:00, 1 March 2024 (UTC)
* Keep.
{{Afd bottom}}"""


class FakeWiki:
    def __init__(self, pages): self.pages = pages
    def log_titles(self, date): return list(self.pages)
    def wikitext(self, title): return self.pages[title]


def test_band_gap_is_semantic_and_does_not_answer_the_window_question():
    from jagged.substrates.afd import band_gap
    assert band_gap(0) == "closed the same day it was nominated"
    assert band_gap(1) == "closed one day after it was nominated"
    assert band_gap(3) == "closed three days after it was nominated"
    for days in (3, 6, 7, 8, 30):
        assert "week" not in band_gap(days), "must not hand over the seven-day verdict"


def test_listing_length_carries_both_forms():
    from jagged.substrates.afd import _listing_length
    dual, gap = _listing_length("[[User:A|A]] 10:00, 1 March 2024 (UTC)\n"
                                "[[User:B|B]] 11:00, 3 March 2024 (UTC)")
    assert gap == 2
    assert dual.raw == "nominated 2024-03-01, closed 2024-03-03"
    assert dual.banded == "closed two days after it was nominated"


def test_an_undated_discussion_is_dropped_not_half_labelled():
    from jagged.substrates.afd import _listing_length
    assert _listing_length("no timestamps here") is None


def test_band_participants_is_semantic_not_numeric():
    assert band_participants(1) == "a single editor"
    assert band_participants(3) == "a handful of editors"
    assert band_participants(12) == "many editors"


def test_stratum_splits_unanimous_from_contested():
    assert stratum_for(2, Close("delete", "delete", "", False)) == "thin_unanimous"
    assert stratum_for(9, Close("no consensus", "no_consensus", "", False)) == "contested"


def test_load_builds_a_valid_labelled_item():
    sub = AfdSubstrate(FakeWiki({"Wikipedia:Articles for deletion/Example Article": DISCUSSION}))
    items = sub.load(budget=1)
    assert len(items) == 1
    item = items[0]
    validate_item(item)
    assert item.labels == {"verdict": True, "window": True}
    assert "discussion" in item.core
    assert "nomination" not in item.core
    assert "participants" in item.numeric
    assert item.numeric["participants"].raw == "3"
    assert item.numeric["participants"].banded == "a handful of editors"
    assert item.temporal["listing_length"].raw == (
        "nominated 2024-03-01, closed 2024-03-01")
    assert item.temporal["listing_length"].banded == (
        "closed the same day it was nominated")


def test_close_text_never_leaks_into_the_item():
    sub = AfdSubstrate(FakeWiki({"Wikipedia:Articles for deletion/Example Article": DISCUSSION}))
    item = sub.load(budget=1)[0]
    blob = " ".join([*item.core.values(), *item.context.values()]).lower()
    assert "the result was" not in blob
    assert "afd top" not in blob


def test_vote_words_do_not_survive_in_any_field():
    """Bolded votes and vote-only lines must leave core and context.

    Attempt 2 put the whole discussion in core, tally included, and baseline
    verdict AUC was 0.997. Padding would hand the votes back if they sat in
    context, so they have to be absent from every field.
    """
    sub = AfdSubstrate(FakeWiki({"Wikipedia:Articles for deletion/Example Article": DISCUSSION}))
    item = sub.load(budget=1)[0]
    blob = "\n".join([*item.core.values(), *item.context.values(),
                      *[d.raw for d in item.numeric.values()],
                      *[d.banded for d in item.numeric.values()],
                      *[d.raw for d in item.temporal.values()],
                      *[d.banded for d in item.temporal.values()]])
    assert "'''Delete'''" not in blob
    assert "'''Keep'''" not in blob
    assert "* Keep." not in blob
    assert "agree with nom" in item.core["discussion"]
    assert "nomination" not in item.core


def test_non_binary_outcomes_are_dropped():
    page = DISCUSSION.replace("'''delete'''", "'''no consensus'''")
    sub = AfdSubstrate(FakeWiki({"Wikipedia:Articles for deletion/X": page}))
    assert sub.load(budget=5) == []
    assert sub.dropped["no_consensus"] == 1
