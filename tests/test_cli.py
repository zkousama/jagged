import json

from jagged.cli import main


def test_analyze_runs_without_api_access(tmp_path, capsys):
    rows = []
    for i in range(20):
        lab = i % 2 == 0
        for arm, p in (("baseline", 0.9 if lab else 0.1), ("placebo", 0.88 if lab else 0.12)):
            # `question` is on every row the runner writes, and analyze reads
            # each arm on the question its manipulation reaches, so a fixture
            # without it is filtered down to nothing.
            rows.append({"item_id": f"i{i}", "arm": arm, "repeat": 0, "probability": p,
                         "label": lab, "stratum": "thin_unanimous",
                         "question": "verdict", "error": None})
    trials = tmp_path / "trials.jsonl"
    trials.write_text("\n".join(json.dumps(r) for r in rows))
    code = main(["analyze", "--trials", str(trials), "--out", str(tmp_path / "figs"),
                 "--n-boot", "200"])
    assert code == 0
    assert "placebo" in capsys.readouterr().out


def test_unknown_command_returns_nonzero(capsys):
    assert main(["frobnicate"]) == 2
