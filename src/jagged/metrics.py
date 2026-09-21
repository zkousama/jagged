import numpy as np
from sklearn.metrics import roc_auc_score


def auc(labels, probs) -> float:
    y = np.asarray(labels, dtype=int)
    if y.min() == y.max():
        return float("nan")
    return float(roc_auc_score(y, np.asarray(probs, dtype=float)))


def accuracy_at(labels, probs, threshold: float = 0.5) -> float:
    y = np.asarray(labels, dtype=int)
    p = np.asarray(probs, dtype=float)
    return float(((p >= threshold).astype(int) == y).mean())


def _binned(labels, probs, bins: int):
    y = np.asarray(labels, dtype=float)
    p = np.asarray(probs, dtype=float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1], right=False), 0, bins - 1)
    for b in range(bins):
        mask = idx == b
        if mask.any():
            yield float(p[mask].mean()), float(y[mask].mean()), int(mask.sum())


def ece(labels, probs, bins: int = 10) -> float:
    n = len(labels)
    return float(sum(count / n * abs(conf - acc)
                     for conf, acc, count in _binned(labels, probs, bins)))


def reliability(labels, probs, bins: int = 10):
    return list(_binned(labels, probs, bins))
