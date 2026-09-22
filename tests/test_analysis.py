import json

import pytest
from jagged.analysis import (PRIMARY_METRICS, Delta, benjamini_hochberg,
                             bootstrap_pvalue, collapse_repeats, family_deltas,
                             load_trials, paired_delta, sensitivity_contrasts,
                             verdict)


def _row(item, arm, repeat, p, label, stratum="thin_unanimous", question="verdict"):
    return {"item_id": item, "arm": arm, "repeat": repeat, "probability": p,
            "label": label, "stratum": stratum, "question": question, "error": None}


def test_load_skips_errored_rows_but_counts_them(tmp_path):
    path = tmp_path / "t.jsonl"
    rows = [_row("a", "baseline", 0, 0.9, True),
            {**_row("b", "baseline", 0, None, False), "error": "429"}]
    path.write_text("\n".join(json.dumps(r) for r in rows))
    trials, dropped = load_trials(path)
    assert len(trials) == 1 and dropped == 1


def test_collapse_repeats_averages_probability_per_item_and_arm():
    rows = [_row("a", "baseline", 0, 0.4, True), _row("a", "baseline", 1, 0.6, True)]
    out = collapse_repeats(rows)
    assert out[("baseline", "a")]["probability"] == pytest.approx(0.5)


def test_paired_delta_is_near_zero_for_identical_arms():
    rows = []
    for i in range(40):
        p, lab = (0.9, True) if i % 2 else (0.1, False)
        rows += [_row(f"i{i}", "baseline", 0, p, lab), _row(f"i{i}", "copy", 0, p, lab)]
    d = paired_delta(rows, "baseline", "copy", metric="auc", n_boot=200, seed=1)
    assert d.point == pytest.approx(0.0, abs=1e-9)
    assert d.lo <= 0.0 <= d.hi


def test_paired_delta_detects_a_degraded_arm():
    rows = []
    for i in range(60):
        lab = i % 2 == 0
        rows.append(_row(f"i{i}", "baseline", 0, 0.95 if lab else 0.05, lab))
        rows.append(_row(f"i{i}", "broken", 0, 0.5, lab))
    d = paired_delta(rows, "baseline", "broken", metric="auc", n_boot=200, seed=1)
    assert d.point < -0.3
    assert d.hi < 0.0


def test_a_delta_ignores_rows_from_another_question():
    """The dates arm is scored on `window`; verdict rows must not leak in."""
    rows = []
    for i in range(40):
        lab = i % 2 == 0
        good, bad = (0.95 if lab else 0.05), 0.5
        rows.append(_row(f"i{i}", "baseline", 0, good, lab, question="window"))
        rows.append(_row(f"i{i}", "dates", 0, bad, lab, question="window"))
        # identical-looking verdict rows that would wash the effect out
        rows.append(_row(f"i{i}", "baseline", 0, good, lab, question="verdict"))
        rows.append(_row(f"i{i}", "dates", 0, good, lab, question="verdict"))
    scoped = paired_delta(rows, "baseline", "dates", metric="auc", n_boot=200,
                          seed=1, question="window")
    unscoped = paired_delta(rows, "baseline", "dates", metric="auc", n_boot=200, seed=1)
    assert scoped.point < -0.3
    assert unscoped.point > scoped.point, "pooling questions hides the effect"


def test_paired_delta_names_the_empty_filter():
    rows = [_row("a", "baseline", 0, 0.9, True, question="verdict"),
            _row("a", "placebo", 0, 0.8, True, question="verdict")]
    with pytest.raises(ValueError, match=r"placebo.*question='window'.*stratum='contested'"):
        paired_delta(rows, "baseline", "placebo", n_boot=10,
                     question="window", stratum="contested")


def test_benjamini_hochberg_rejects_only_small_pvalues():
    assert benjamini_hochberg([0.001, 0.04, 0.8], q=0.05) == [True, False, False]


def test_bootstrap_pvalue_floors_at_one_over_n_boot_plus_one():
    """No draw on the far side of zero: the p-value is 1/(n_boot+1), not zero."""
    draws = [-0.2] * 200
    assert bootstrap_pvalue(-0.2, draws, n_boot=200) == pytest.approx(1 / 201)


def test_bootstrap_pvalue_is_twice_the_far_side_share():
    draws = [-0.1] * 90 + [0.05] * 10
    assert bootstrap_pvalue(-0.1, draws, n_boot=100) == pytest.approx(0.20)


def test_paired_delta_carries_a_bootstrap_pvalue_at_the_floor():
    rows = []
    for i in range(60):
        lab = i % 2 == 0
        rows.append(_row(f"i{i}", "baseline", 0, 0.95 if lab else 0.05, lab))
        rows.append(_row(f"i{i}", "broken", 0, 0.5, lab))
    d = paired_delta(rows, "baseline", "broken", metric="auc", n_boot=200, seed=1)
    assert d.pvalue == pytest.approx(1 / 201)


def test_sensitivity_contrast_is_the_arm_minus_placebo():
    """A sensitivity row is a paired delta against placebo, not against baseline."""
    rows = []
    for i in range(40):
        lab = i % 2 == 0
        ok, mid, bad = (0.95 if lab else 0.05), (0.7 if lab else 0.3), 0.5
        rows += [_row(f"i{i}", "baseline", 0, ok, lab),
                 _row(f"i{i}", "placebo", 0, mid, lab),
                 _row(f"i{i}", "broken", 0, bad, lab)]
    got = sensitivity_contrasts(rows, n_boot=50, seed=1)
    want = paired_delta(rows, "placebo", "broken", metric="accuracy",
                        n_boot=50, seed=1, question="verdict")
    assert ("broken", "accuracy") in got
    assert got[("broken", "accuracy")].point == pytest.approx(want.point)
    assert got[("broken", "accuracy")].lo == pytest.approx(want.lo)
    assert "placebo" not in {a for a, _ in got}
    assert "baseline" not in {a for a, _ in got}


def test_family_deltas_is_arms_times_both_primaries():
    """The FDR family is every non-baseline arm × accuracy and ECE, not AUC."""
    rows = []
    for i in range(40):
        lab = i % 2 == 0
        ok, bad = (0.9 if lab else 0.1), 0.5
        rows += [_row(f"i{i}", "baseline", 0, ok, lab),
                 _row(f"i{i}", "broken", 0, bad, lab),
                 _row(f"i{i}", "placebo", 0, ok, lab)]
    family = family_deltas(rows, n_boot=50, seed=1)
    assert PRIMARY_METRICS == ("accuracy", "ece")
    assert set(family) == {
        ("broken", "accuracy"), ("broken", "ece"),
        ("placebo", "accuracy"), ("placebo", "ece"),
    }
    assert all(m != "auc" for _, m in family)


def test_verdict_requires_clearing_zero_and_the_placebo():
    real = Delta(point=-0.20, lo=-0.28, hi=-0.12)
    noise = Delta(point=-0.01, lo=-0.05, hi=0.03)
    placebo = Delta(point=0.00, lo=-0.06, hi=0.06)
    assert verdict(real, placebo, survived_fdr=True) == "effect"
    assert verdict(real, placebo, survived_fdr=False) == "null"
    assert verdict(noise, placebo, survived_fdr=True) == "null"
