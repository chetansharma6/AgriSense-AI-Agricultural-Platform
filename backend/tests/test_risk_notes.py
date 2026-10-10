import pytest

from app.scoring import climate_risk_notes


@pytest.mark.parametrize(("flag", "label"), [
    ("Season averages 27.5 C, warmer than the ideal 15-25 C: heat stress risk", "Excessive heat"),
    ("About 3.0 freezing nights in season, 3.0 of them hard (-2 C or colder); protect tender crops", "Frost exposure"),
    ("Season rainfall 300 mm is above the ideal 100-200 mm: watch for disease and leaching", "Excessive rainfall"),
    ("Likely needs irrigation (50 mm rain expected, 100 mm needed)", "Dry-season irrigation pressure"),
])
def test_risk_note_uses_existing_factor_flag(flag: str, label: str) -> None:
    assert climate_risk_notes([flag]) == [f"{label}: {flag}"]


def test_unrelated_flags_do_not_create_climate_risks() -> None:
    assert climate_risk_notes(["Soil pH 5.3 is below the ideal 5.8-6.5: lime may be needed"]) == []
