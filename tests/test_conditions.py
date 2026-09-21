import pytest
from jagged.conditions import ARM_NAMES, ARMS, render
from jagged.items import Item, Dual
from jagged.question import QuestionSpec

ITEM = Item(
    id="afd:X",
    core={"nomination": "Fails WP:GNG.", "discussion": "*Delete per nom."},
    context={"signatures": "[[User:A|A]] (UTC)", "procedural": "{{AFD help}}"},
    numeric={"participants": Dual(raw="3", banded="a handful of editors")},
    temporal={"listing_length": Dual(
        raw="nominated 2024-03-08, closed 2024-03-11",
        banded="closed three days after it was nominated")},
    labels={"verdict": True, "window": True},
    stratum="thin_unanimous",
)
SPECS = {
    "verdict": QuestionSpec(
        instructions="Answer whether the article was deleted.",
        criteria={"true": "The closer deleted the article.",
                  "false": "The closer kept the article."},
        boundary="Treat a redirect or a merge as not deleted.",
    ),
    "window": QuestionSpec(
        instructions="Answer whether it closed before seven days had elapsed.",
        criteria={"true": "Closed sooner than seven days.",
                  "false": "Open seven days or longer."},
    ),
}

EXPECTED_DIFF = {
    "baseline":      set(),
    "literal":       {"criteria"},
    "numbers":       {"state:participants"},
    "dates":         {"state:listing_length"},
    "indirection":   {"instructions"},
    "context_25":    {"state:+context"},
    "context_50":    {"state:+context"},
    "context_100":   {"state:+context"},
    "criteria":      {"criteria"},
    "adversarial":   {"state:+context"},
    "placebo":       {"state:order"},
}


def _diff(base, arm):
    bs, bq = base
    as_, aq = arm
    out = set()
    if as_.keys() != bs.keys():
        out.add("state:+context")
    for k in bs.keys() & as_.keys():
        if bs[k] != as_[k]:
            out.add(f"state:{k}")
    if list(as_.keys()) != list(bs.keys()) and as_.keys() == bs.keys():
        out.add("state:order")
    for name in bq:
        if aq[name].instructions != bq[name].instructions:
            out.add("instructions")
        if aq[name].rendered_criteria != bq[name].rendered_criteria:
            out.add("criteria")
    return out


def test_every_arm_is_named_once():
    assert sorted(ARM_NAMES) == sorted(ARMS)
    assert len(ARM_NAMES) == 11


@pytest.mark.parametrize("arm", list(EXPECTED_DIFF))
def test_arm_changes_exactly_one_variable(arm):
    base = render(ITEM, SPECS, "baseline")
    got = _diff(base, render(ITEM, SPECS, arm))
    assert got == EXPECTED_DIFF[arm], f"{arm} changed {got}, expected {EXPECTED_DIFF[arm]}"


@pytest.mark.parametrize("arm", ["literal", "indirection", "criteria"])
def test_question_level_arms_leave_the_other_questions_alone(arm):
    _, specs = render(ITEM, SPECS, arm)
    assert specs["window"] == SPECS["window"], f"{arm} reworded a question it does not own"
    assert specs["verdict"] != SPECS["verdict"], f"{arm} changed nothing"


def test_baseline_is_docs_compliant():
    state, specs = render(ITEM, SPECS, "baseline")
    assert state["participants"] == "a handful of editors", "numbers must be banded"
    assert "2024-03-11" not in " ".join(state.values()), "dates must be resolved"
    assert "signatures" not in state, "context must be excluded"
    assert "Treat a redirect" in specs["verdict"].rendered_criteria["false"], \
        "boundary goes in criteria"


def test_the_window_question_actually_reads_the_dates():
    """Mode 3 is only a date manipulation if some judgment consumes the field."""
    base_state, _ = render(ITEM, SPECS, "baseline")
    dates_state, _ = render(ITEM, SPECS, "dates")
    assert base_state["listing_length"] != dates_state["listing_length"]
    assert "2024-03-08" in dates_state["listing_length"], "raw form must carry both dates"
    assert "three days" in base_state["listing_length"], "banded form is the computed gap"
    assert "week" not in base_state["listing_length"], "baseline must not state the answer"


def test_placebo_preserves_content_exactly():
    base_state, _ = render(ITEM, SPECS, "baseline")
    pl_state, _ = render(ITEM, SPECS, "placebo")
    assert base_state == pl_state, "placebo changes order only, never values"
    assert list(base_state) != list(pl_state), "placebo must actually reorder"


def test_context_doses_are_strictly_increasing_in_volume():
    def padding_chars(arm):
        state, _ = render(ITEM, SPECS, arm)
        base, _ = render(ITEM, SPECS, "baseline")
        return sum(len(v) for k, v in state.items() if k not in base)

    volumes = [padding_chars(a) for a in ("context_25", "context_50", "context_100")]
    assert volumes[0] < volumes[1] < volumes[2], f"doses collapsed: {volumes}"
