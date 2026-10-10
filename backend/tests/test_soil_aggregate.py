import pytest

from app.clients.soil import (
    combine_components, component_values, summarize_soil, texture_class, top_layer_mean,
)


def horizon(cokey: str, pct: float | None, top: float, bottom: float, ph: float | None = None,
            om: float | None = None, sand: float | None = None, clay: float | None = None,
            name: str = "Test", drainage: str | None = "Well drained") -> dict:
    return {"cokey": cokey, "compname": name, "comppct_r": pct, "drainagecl": drainage,
            "majcompflag": "Yes", "hzdept_r": top, "hzdepb_r": bottom, "ph1to1h2o_r": ph,
            "om_r": om, "sandtotal_r": sand, "claytotal_r": clay}


def test_horizon_starting_at_25_cm_counts_for_5_cm() -> None:
    rows = [horizon("a", 100, 0, 25, ph=5.0), horizon("a", 100, 25, 60, ph=7.0)]
    # (25 * 5.0 + 5 * 7.0) / 30
    assert top_layer_mean(rows, "ph1to1h2o_r") == pytest.approx(160 / 30)


def test_horizons_below_30_cm_are_ignored() -> None:
    rows = [horizon("a", 100, 0, 30, ph=5.0), horizon("a", 100, 30, 80, ph=8.0)]
    assert top_layer_mean(rows, "ph1to1h2o_r") == 5.0


def test_component_with_all_ph_none_is_skipped() -> None:
    rows = [
        horizon("a", 60, 0, 30, ph=6.0, sand=90, clay=4, name="Major"),
        horizon("b", 40, 0, 30, ph=None, sand=80, clay=10, name="Minor"),
    ]
    components = component_values(rows)
    assert [c["soil_ph"] for c in components] == [6.0, None]
    # pH comes from component a alone (weights renormalized); sand from both.
    assert combine_components(components, "soil_ph") == 6.0
    assert combine_components(components, "sand_pct") == pytest.approx(86.0)


def test_summarize_muck_soil() -> None:
    rows = [
        horizon("a", 85, 0, 20, om=60, name="Torry", drainage="Very poorly drained"),
        horizon("a", 85, 20, 80, om=40, name="Torry", drainage="Very poorly drained"),
        horizon("b", 15, None, None, name="Water", drainage=None),
    ]
    soil = summarize_soil(rows, "1407305")
    assert soil == {
        "soil_ph": None, "organic_matter_pct": 53.3, "sand_pct": None, "clay_pct": None,
        "texture": "muck", "drainage": "Very poorly drained", "mukey": "1407305",
        "dominant_component": "Torry", "source": "USDA NRCS SSURGO",
    }


def test_drainage_from_largest_component_with_a_value() -> None:
    rows = [horizon("a", 70, 0, 30, drainage=None, name="Big"),
            horizon("b", 30, 0, 30, drainage="Poorly drained", name="Small")]
    soil = summarize_soil(rows, "1")
    assert soil["drainage"] == "Poorly drained"
    assert soil["dominant_component"] == "Big"


@pytest.mark.parametrize("sand,clay,om,expected", [
    (None, None, 35.0, "muck"),
    (94, 5, 5.0, "sand"),
    (81, 10, 0.8, "loamy sand"),
    (60, 15, None, "sandy loam"),
    (20, 40, None, "clay"),
    (30, 30, None, "clay loam"),
    (40, 20, None, "loam"),
    (None, 10, None, None),
])
def test_texture_class(sand: float | None, clay: float | None, om: float | None,
                       expected: str | None) -> None:
    assert texture_class(sand, clay, om) == expected
