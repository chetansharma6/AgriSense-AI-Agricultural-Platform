from typing import Any

import pandas as pd
import pytest
from pydantic import ValidationError

from app.climate import SeasonStats
from app.crops import Crop, load_crops
from app.market import CountyAcreage
from app.scoring import (
    best_window, range_score, relative_range_score, score_climate, score_drainage, score_local_history,
    score_ph, trapezoid_score, weighted_score,
)

NAN = float("nan")


def make_crop(**overrides: Any) -> Crop:
    """A small fake crop with round numbers, independent of crops.json."""
    raw = {
        "id": "fake", "name": "Fake", "nass_commodity": "FAKE", "nass_class": None,
        "nass": {"acres_descs": ["FAKE - ACRES HARVESTED"],
                 "yield_desc": "FAKE - YIELD, MEASURED IN LB / ACRE",
                 "price_desc": "FAKE - PRICE RECEIVED, MEASURED IN $ / LB"},
        "fl_windows": [
            {"label": "Winter: plant Jan", "start": "01-01", "end": "03-31", "months": [1, 2, 3]},
            {"label": "Summer: plant Jun", "start": "06-01", "end": "08-31", "months": [6, 7, 8]},
        ],
        "ph_min": 4.5, "ph_ideal_min": 5.5, "ph_ideal_max": 6.5, "ph_max": 7.5,
        "drainage": ["Well drained", "Somewhat poorly drained"], "muck_suitable": False,
        "temp_min_c": 10, "temp_ideal_min_c": 15, "temp_ideal_max_c": 25, "temp_max_c": 30,
        "max_freeze_days": 2, "rain_mm_per_month": [100, 200],
        "general_guidance": "", "extension_links": [], "source_notes": "", "needs_review": False,
        "min_practical_acres": 10, "small_acres": 2, "scale_note": "Equipment and market access matter.",
        "n_lb_per_acre": 100,
        "nutrient_source": {"title": "Test source", "url": "https://edis.ifas.ufl.edu/"},
        "evidence": {"nutrient_status": "verified", "nitrogen_recommendation_type": "fixed",
                     "nitrogen_note": "Test evidence.", "source_verified": True},
    }
    return Crop.model_validate({**raw, **overrides})


CROP = make_crop()


def stats(temp: float = 20.0, freezes: float = 0.0, rain: float = 150.0, months: float = 1.0,
          hard: float | None = None) -> SeasonStats:
    """One-month season, so the rainfall ideal is exactly 100-200 mm. By default every freeze is hard."""
    return SeasonStats(mean_temp_c=temp, freeze_days=freezes, precip_mm=rain, months=months,
                       hard_freeze_days=freezes if hard is None else hard)


# --- shape helpers -----------------------------------------------------------

def test_range_score() -> None:
    assert range_score(5.5, 5.0, 6.0, 40) == 100
    assert range_score(5.0, 5.0, 6.0, 40) == 100
    assert range_score(6.0, 5.0, 6.0, 40) == 100
    assert range_score(4.5, 5.0, 6.0, 40) == 80
    assert range_score(6.5, 5.0, 6.0, 40) == 80
    assert range_score(20.0, 5.0, 6.0, 40) == 0


def test_trapezoid_score() -> None:
    assert trapezoid_score(5.5, 4.0, 5.0, 6.0, 7.0) == 100
    assert trapezoid_score(5.0, 4.0, 5.0, 6.0, 7.0) == 100
    assert trapezoid_score(6.0, 4.0, 5.0, 6.0, 7.0) == 100
    assert trapezoid_score(4.5, 4.0, 5.0, 6.0, 7.0) == 50
    assert trapezoid_score(6.75, 4.0, 5.0, 6.0, 7.0) == 25
    assert trapezoid_score(4.0, 4.0, 5.0, 6.0, 7.0) == 0
    assert trapezoid_score(7.0, 4.0, 5.0, 6.0, 7.0) == 0
    assert trapezoid_score(3.0, 4.0, 5.0, 6.0, 7.0) == 0
    assert trapezoid_score(9.0, 4.0, 5.0, 6.0, 7.0) == 0


def test_relative_range_score() -> None:
    assert relative_range_score(400, 350, 600) == 100
    assert relative_range_score(350, 350, 600) == 100
    assert relative_range_score(600, 350, 600) == 100
    assert relative_range_score(315, 350, 600) == 90
    assert relative_range_score(660, 350, 600) == 90
    assert relative_range_score(0, 350, 600) == 0
    assert relative_range_score(1200, 350, 600) == 0
    assert relative_range_score(5000, 350, 600) == 0


# --- soil pH -----------------------------------------------------------------

@pytest.mark.parametrize("ph", [6.0, 5.5, 6.5])
def test_ph_inside_and_on_ideal_bounds(ph: float) -> None:
    assert score_ph(CROP, ph) == (100, {"value": ph, "ideal": "5.5-6.5", "unit": "pH"}, [])


@pytest.mark.parametrize("ph", [4.5, 7.5, 3.0, 9.0])
def test_ph_at_or_beyond_hard_limits(ph: float) -> None:
    assert score_ph(CROP, ph)[0] == 0


def test_ph_below_ideal_flags_lime() -> None:
    score, _, flags = score_ph(CROP, 5.0)
    assert score == 50
    assert flags == ["Soil pH 5 is below the ideal 5.5-6.5: lime may be needed"]


def test_ph_above_ideal_flags_sulfur() -> None:
    score, _, flags = score_ph(CROP, 7.0)
    assert score == 50
    assert flags == ["Soil pH 7 is above the ideal 5.5-6.5: sulfur or acid-forming fertilizer may help"]


@pytest.mark.parametrize("ph", [None, NAN])
def test_ph_missing(ph: float | None) -> None:
    score, detail, flags = score_ph(CROP, ph)
    assert score is None and flags == []
    assert detail["value"] is None  # never NaN: it must serialize to JSON


# --- drainage ----------------------------------------------------------------

@pytest.mark.parametrize("drainage", ["Well drained", "Moderately well drained", "Somewhat poorly drained"])
def test_drainage_inside_and_on_bounds(drainage: str) -> None:
    score, detail, flags = score_drainage(CROP, drainage, "sand")
    assert (score, flags) == (100, [])
    assert detail == {"value": drainage, "ideal": "Well drained to somewhat poorly drained"}


def test_drainage_one_class_wetter() -> None:
    score, _, flags = score_drainage(CROP, "Poorly drained", "sand")
    assert score == 75
    assert flags == ["Poorly drained soil is wetter than ideal (well drained to somewhat poorly drained): "
                     "use raised beds or improve drainage"]


def test_drainage_one_class_drier() -> None:
    score, _, flags = score_drainage(CROP, "Somewhat excessively drained", "sand")
    assert score == 75
    assert flags == ["Somewhat excessively drained soil is drier than ideal (well drained to somewhat poorly "
                     "drained): plan for irrigation and organic matter"]
    assert "irrigation" in flags[0]  # the frontend's "Needs irrigation" filter matches this word


def test_drainage_two_classes_away() -> None:
    assert score_drainage(CROP, "Very poorly drained", "sand")[0] == 50
    assert score_drainage(CROP, "Excessively drained", "sand")[0] == 50


def test_drainage_far_away_floors_at_zero() -> None:
    narrow = make_crop(drainage=["Excessively drained", "Excessively drained"])
    assert score_drainage(narrow, "Very poorly drained", "sand")[0] == 0


@pytest.mark.parametrize("drainage", [None, "Not a drainage class"])
def test_drainage_missing(drainage: str | None) -> None:
    assert score_drainage(CROP, drainage, "sand") == (None, {"value": drainage, "ideal": "Well drained to somewhat "
                                                                                 "poorly drained"}, [])


def test_muck_overrides_drainage_class() -> None:
    muck_crop = make_crop(muck_suitable=True)
    assert score_drainage(muck_crop, None, "muck")[0] == 90
    assert score_drainage(CROP, "Well drained", "muck") == (
        15, {"value": "Well drained", "ideal": "Well drained to somewhat poorly drained"},
        ["Muck soil: not typical for this crop"])


# --- season temperature ------------------------------------------------------

@pytest.mark.parametrize("temp", [20.0, 15.0, 25.0])
def test_temp_inside_and_on_ideal_bounds(temp: float) -> None:
    assert score_climate(CROP, stats(temp=temp))["season_temp"] == (
        100, {"value": temp, "ideal": "15-25", "unit": "C avg"}, [])


@pytest.mark.parametrize("temp", [10.0, 30.0, 5.0, 35.0])
def test_temp_at_or_beyond_hard_limits(temp: float) -> None:
    assert score_climate(CROP, stats(temp=temp))["season_temp"][0] == 0


def test_temp_cooler_than_ideal() -> None:
    score, _, flags = score_climate(CROP, stats(temp=12.5))["season_temp"]
    assert score == 50
    assert flags == ["Season averages 12.5 C, cooler than the ideal 15-25 C: slower growth"]


def test_temp_warmer_than_ideal() -> None:
    score, _, flags = score_climate(CROP, stats(temp=27.5))["season_temp"]
    assert score == 50
    assert flags == ["Season averages 27.5 C, warmer than the ideal 15-25 C: heat stress risk"]


# --- frost risk --------------------------------------------------------------

FROST_UNIT = "freeze days in season (light freezes count half)"


@pytest.mark.parametrize("freezes", [0.0, 1.5, 2.0])
def test_frost_within_tolerance(freezes: float) -> None:
    assert score_climate(CROP, stats(freezes=freezes))["frost_risk"] == (
        100, {"value": freezes, "ideal": "<= 2", "unit": FROST_UNIT}, [])


def test_frost_over_tolerance_loses_ten_per_day() -> None:
    score, _, flags = score_climate(CROP, stats(freezes=3.0))["frost_risk"]
    assert score == 90
    assert flags == ["About 3.0 freezing nights in season, 3.0 of them hard (-2 C or colder); "
                     "crop tolerates about 2: plan frost protection or a later planting"]


def test_light_freezes_count_half() -> None:
    # Four nights between -2 and 0 C weigh the same as two hard freezes: still within tolerance.
    assert score_climate(CROP, stats(freezes=4.0, hard=0.0))["frost_risk"][:2] == (
        100, {"value": 2.0, "ideal": "<= 2", "unit": FROST_UNIT})
    # One hard + three light = 2.5 weighted days: half a day over.
    assert score_climate(CROP, stats(freezes=4.0, hard=1.0))["frost_risk"][0] == 95


def test_missing_hard_freeze_count_is_missing() -> None:
    assert score_climate(CROP, stats(freezes=1.0, hard=float("nan")))["frost_risk"][0] is None


def test_frost_floors_at_zero() -> None:
    assert score_climate(CROP, stats(freezes=40.0))["frost_risk"][0] == 0


# --- rainfall ----------------------------------------------------------------

@pytest.mark.parametrize("rain", [150.0, 100.0, 200.0])
def test_rain_inside_and_on_ideal_bounds(rain: float) -> None:
    assert score_climate(CROP, stats(rain=rain))["rainfall"] == (
        100, {"value": round(rain), "ideal": "100-200", "unit": "mm in season"}, [])


def test_rain_ideal_scales_with_season_length() -> None:
    assert score_climate(CROP, stats(rain=450.0, months=3))["rainfall"][1]["ideal"] == "300-600"


def test_rain_below_ideal_flags_irrigation() -> None:
    score, _, flags = score_climate(CROP, stats(rain=50.0))["rainfall"]
    assert score == 50
    assert flags == ["Likely needs irrigation (50 mm rain expected, 100 mm needed)"]


def test_rain_above_ideal_flags_disease() -> None:
    score, _, flags = score_climate(CROP, stats(rain=300.0))["rainfall"]
    assert score == 50
    assert flags == ["Season rainfall 300 mm is above the ideal 100-200 mm: watch for disease and leaching"]


def test_rain_far_outside_floors_at_zero() -> None:
    assert score_climate(CROP, stats(rain=0.0))["rainfall"][0] == 0
    assert score_climate(CROP, stats(rain=1000.0))["rainfall"][0] == 0


# --- climate missing data ----------------------------------------------------

def test_climate_without_weather() -> None:
    result = score_climate(CROP, None)
    assert {name: factor[0] for name, factor in result.items()} == dict.fromkeys(result)
    assert all(factor[2] == [] for factor in result.values())


def test_nan_temperature_is_missing_not_perfect() -> None:
    result = score_climate(CROP, stats(temp=NAN))
    assert result["season_temp"] == (None, {"value": None, "ideal": "15-25", "unit": "C avg"}, [])
    assert result["frost_risk"][0] == 100
    assert result["rainfall"][0] == 100


def test_nan_rain_and_freezes_are_missing() -> None:
    result = score_climate(CROP, stats(freezes=NAN, rain=NAN))
    assert result["frost_risk"][0] is None and result["frost_risk"][1]["value"] is None
    assert result["rainfall"][0] is None and result["rainfall"][1]["value"] is None
    assert result["season_temp"][0] == 100


# --- local history -----------------------------------------------------------

def test_local_history() -> None:
    assert score_local_history(None)[0] is None
    assert score_local_history(CountyAcreage(year=None, acres=None))[0] == 30
    assert score_local_history(CountyAcreage(year=2022, acres=None))[0] == 75
    assert score_local_history(CountyAcreage(year=2022, acres=1))[0] == 60
    assert score_local_history(CountyAcreage(year=2022, acres=5000))[0] == 100
    assert score_local_history(CountyAcreage(year=2022, acres=50000))[0] == 100  # capped
    assert 60 < score_local_history(CountyAcreage(year=2022, acres=100))[0] < 100


def test_local_history_not_grown_flags_market() -> None:
    _, detail, flags = score_local_history(CountyAcreage(year=None, acres=None))
    assert detail["value"] == "Not reported in county"
    assert flags == ["Not reported in this county: confirm local buyers and markets"]


# --- combining factors -------------------------------------------------------

def test_weighted_score_skips_missing_factors() -> None:
    factors = {"soil_ph": None, "drainage": 100, "season_temp": 100, "frost_risk": 100,
               "rainfall": 100, "local_history": 0}
    assert weighted_score(factors) == round(100 * 0.60 / 0.80)
    assert weighted_score(dict.fromkeys(factors)) is None


def test_weighted_score_all_perfect() -> None:
    assert weighted_score(dict.fromkeys(["soil_ph", "drainage", "season_temp", "frost_risk", "rainfall",
                                         "local_history"], 100)) == 100


def test_best_window_picks_the_warm_season() -> None:
    days = pd.date_range("2016-01-01", "2019-12-31", freq="D")
    cold = days.month.isin([1, 2, 3])
    weather = pd.DataFrame({
        "t_mean_c": [2.0 if c else 20.0 for c in cold],
        "t_min_c": [-5.0 if c else 15.0 for c in cold],
        "precip_mm": 5.0,
    }, index=days)
    window, climate = best_window(CROP, weather)
    assert window.label == "Summer: plant Jun"
    assert climate["season_temp"][0] == 100
    assert climate["frost_risk"][0] == 100


def test_best_window_without_weather_uses_first_window() -> None:
    window, climate = best_window(CROP, None)
    assert window.label == "Winter: plant Jan"
    assert all(factor[0] is None for factor in climate.values())


# --- crop table validation ---------------------------------------------------

def test_real_crop_table_is_valid() -> None:
    assert len(load_crops()) == 13


@pytest.mark.parametrize("overrides", [
    {"ph_min": 5.5},                                     # hard limit equals ideal: divides by zero
    {"ph_ideal_min": 7.0},                               # ideal band reversed
    {"temp_max_c": 25},                                  # hard limit equals ideal
    {"rain_mm_per_month": [0, 200]},                     # zero divides relative_range_score
    {"rain_mm_per_month": [300, 200]},
    {"max_freeze_days": -1},
    {"drainage": ["Poorly drained", "Well drained"]},    # wettest listed first
    {"drainage": ["Well drained", "Soggy"]},
    {"fl_windows": []},
    {"fl_windows": [{"label": "x", "start": "13-01", "end": "03-31", "months": [1]}]},
    {"fl_windows": [{"label": "x", "start": "01-01", "end": "03-31", "months": [0]}]},
])
def test_invalid_crop_rejected(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        make_crop(**overrides)
