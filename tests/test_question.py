from jagged.question import QuestionSpec


def test_to_noul_carries_instructions_only_when_criteria_absent():
    spec = QuestionSpec(instructions="Was this article deleted?")
    noul = spec.to_noul()
    assert noul.instructions == "Was this article deleted?"
    assert getattr(noul, "criteria", None) is None


def test_boundary_lands_in_the_false_criterion():
    spec = QuestionSpec(
        instructions="Was this article deleted?",
        criteria={"true": "The closer removed it.", "false": "The closer kept it."},
        boundary="Treat a redirect as not deleted.",
    )
    assert spec.instructions == "Was this article deleted?"
    assert spec.rendered_criteria["false"] == (
        "The closer kept it. Treat a redirect as not deleted."
    )
    assert spec.rendered_criteria["true"] == "The closer removed it."


def test_dropping_the_boundary_changes_only_that_field():
    full = QuestionSpec(instructions="x", criteria={"true": "a", "false": "b"}, boundary="y.")
    stripped = QuestionSpec(instructions="x", criteria={"true": "a", "false": "b"})
    assert full.instructions == stripped.instructions
    assert full.rendered_criteria["true"] == stripped.rendered_criteria["true"]
    assert full.rendered_criteria["false"] != stripped.rendered_criteria["false"]


def test_to_noul_carries_criteria_when_present():
    spec = QuestionSpec(
        instructions="Was this article deleted?",
        criteria={"true": "The closer removed the article.", "false": "The article was retained."},
    )
    noul = spec.to_noul()
    assert noul.criteria == {"true": "The closer removed the article.",
                             "false": "The article was retained."}


def test_specs_compare_structurally():
    a = QuestionSpec(instructions="x")
    b = QuestionSpec(instructions="x")
    assert a == b
    assert a != QuestionSpec(instructions="y")
