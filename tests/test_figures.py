import json

from jagged.analysis import Delta
from jagged.figures import degradation_curves, forest_plot


def _rows(tmp_path):
    rows = []
    for i in range(30):
        lab = i % 2 == 0
        stratum = "thin_unanimous" if i < 15 else "well_attended"
        rows.append({"item_id": f"i{i}", "arm": "baseline", "repeat": 0,
                     "probability": 0.9 if lab else 0.1, "label": lab,
                     "stratum": stratum, "error": None})
        rows.append({"item_id": f"i{i}", "arm": "context_100", "repeat": 0,
                     "probability": 0.6 if lab else 0.4, "label": lab,
                     "stratum": stratum, "error": None})
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows))
    return p


def test_degradation_curves_writes_a_png(tmp_path):
    out = degradation_curves(_rows(tmp_path), tmp_path / "fig1.png", n_boot=200)
    assert out.exists() and out.stat().st_size > 1000


def test_forest_plot_writes_a_png(tmp_path):
    deltas = {"context_100": Delta(-0.18, -0.26, -0.10),
              "numbers": Delta(-0.04, -0.09, 0.01)}
    out = forest_plot(deltas, Delta(0.0, -0.05, 0.05), tmp_path / "fig4.png")
    assert out.exists() and out.stat().st_size > 1000
