import copy

from scripts import evaluate_demos


def test_all_committed_demos_pass_offline_evaluation() -> None:
    reports, errors = evaluate_demos.run()
    assert errors == []
    assert set(reports) == {"marianna", "hastings", "plant_city", "belle_glade"}
    assert all(report["crop_count"] == 13 for report in reports.values())
    assert all(report["deterministic"] and report["finite"] for report in reports.values())


def test_evaluator_reports_failures_and_nonzero_exit(monkeypatch) -> None:
    response = {
        "crops": [{"score": float("nan"), "factors": {"rainfall": None}}],
        "provenance": {"mode": "live", "sources": []},
    }
    report, errors = evaluate_demos._evaluate("broken", response, copy.deepcopy(response), 1_500)
    assert report["finite"] is False
    assert report["missing_factors"] == ["rainfall"]
    assert any("latency" in error for error in errors)
    assert any("NaN/infinity" in error for error in errors)

    monkeypatch.setattr(evaluate_demos, "run", lambda: ({"broken": report}, errors))
    assert evaluate_demos.main() == 1
