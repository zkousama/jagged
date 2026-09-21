import pytest
from jagged.metrics import accuracy_at, auc, ece, reliability


def test_auc_is_one_for_perfect_separation():
    assert auc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == pytest.approx(1.0)


def test_auc_is_half_for_no_signal():
    assert auc([0, 1, 0, 1], [0.5, 0.5, 0.5, 0.5]) == pytest.approx(0.5)


def test_accuracy_uses_the_documented_half_threshold():
    assert accuracy_at([1, 0], [0.6, 0.4]) == pytest.approx(1.0)
    assert accuracy_at([1, 0], [0.4, 0.6]) == pytest.approx(0.0)


def test_ece_is_zero_for_perfectly_calibrated_predictions():
    labels = [1] * 90 + [0] * 10
    probs = [0.9] * 100
    assert ece(labels, probs, bins=10) == pytest.approx(0.0, abs=1e-9)


def test_ece_is_large_when_confident_and_wrong():
    assert ece([0] * 100, [0.99] * 100, bins=10) == pytest.approx(0.99, abs=1e-6)


def test_reliability_returns_populated_bins_only():
    # 0.9 and 0.95 share the top bin; 0.1 sits in its own. 0.85 would be a third.
    bins = reliability([1, 0, 1], [0.9, 0.1, 0.95], bins=10)
    assert all(count > 0 for _, _, count in bins)
    assert len(bins) == 2
    assert sorted(count for _, _, count in bins) == [1, 2]
