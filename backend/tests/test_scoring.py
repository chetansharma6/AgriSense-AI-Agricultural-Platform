from app.crops import load_crops
from app.market import CountyAcreage
from app.scoring import (
    range_score, relative_range_score, trapezoid_score, score_drainage, score_local_history, score_ph, weighted_score,
)

POTATO = load_crops()["potato"]
SUGARCANE = load_crops()["sugarcane"]


def test_range_score() -> None:
    assert range_score(5.5, 5.0, 6.0, 40) == 100
    assert range_score(6.5, 5.0, 6.0, 40) == 80
    assert range_score(20.0, 5.0, 6.0, 40) == 0


def test_relative_range_score() -> None:
    assert relative_range_score(400, 350, 600) == 100
    assert relative_range_score(175, 350, 600) == 50
    assert relative_range_score(1200, 350, 600) == 0


def test_trapezoid_score() -> None:
    assert trapezoid_score(5.5, 4.0, 5.0, 6.0, 7.0) == 100
    assert trapezoid_score(4.5, 4.0, 5.0, 6.0, 7.0) == 50
    assert trapezoid_score(6.75, 4.0, 5.0, 6.0, 7.0) == 25
    assert trapezoid_score(3.0, 4.0, 5.0, 6.0, 7.0) == 0


def test_score_ph_flags_acidic_soil() -> None:
    score, detail, flags = score_ph(POTATO, 4.5)
    assert score == round(100 * (4.5 - 4.3) / (5.0 - 4.3))
    assert detail == {"value": 4.5, "ideal": "5-6", "unit": "pH"}
    assert flags == ["Soil is more acidic than ideal: lime may be needed"]


def test_score_ph_missing() -> None:
    assert score_ph(POTATO, None)[0] is None


def test_score_drainage() -> None:
    assert score_drainage(POTATO, "Well drained", "sand")[0] == 100
    score, detail, flags = score_drainage(POTATO, "Poorly drained", "sand")
    assert score == 75
    assert detail["ideal"] == "Well drained to somewhat poorly drained"
    assert flags


def test_muck_depends_on_crop() -> None:
    assert score_drainage(SUGARCANE, "Very poorly drained", "muck")[0] == 90
    assert score_drainage(POTATO, "Very poorly drained", "muck")[0] == 30


def test_local_history() -> None:
    assert score_local_history(None)[0] is None
    assert score_local_history(CountyAcreage(year=None, acres=None))[0] == 30
    assert score_local_history(CountyAcreage(year=2022, acres=None))[0] == 75
    assert score_local_history(CountyAcreage(year=2022, acres=5000))[0] == 100
    assert score_local_history(CountyAcreage(year=2022, acres=1))[0] == 60


def test_weighted_score_skips_missing_factors() -> None:
    factors = {"soil_ph": None, "drainage": 100, "season_temp": 100, "frost_risk": 100,
               "rainfall": 100, "local_history": 0}
    assert weighted_score(factors) == round(100 * 0.60 / 0.85)
    assert weighted_score(dict.fromkeys(factors)) is None
