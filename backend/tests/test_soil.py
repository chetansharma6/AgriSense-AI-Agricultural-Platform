import pytest

from app.clients import soil
from tests.fakes import FakeClient

COLUMNS = ["muname", "compname", "comppct_r", "drainagecl",
           "ph1to1h2o_r", "om_r", "sandtotal_r", "claytotal_r"]


def test_get_soil_parses_dominant_component(monkeypatch: pytest.MonkeyPatch) -> None:
    row = ["Floridana fine sand", "Floridana", "90", "Very poorly drained", "5.8", "5", "94", "5"]
    monkeypatch.setattr(soil, "http", lambda: FakeClient({"Table": [COLUMNS, row]}))

    result = soil.get_soil(29.71, -81.50)
    assert result == {
        "soil_ph": 5.8, "organic_matter_pct": 5.0, "sand_pct": 94.0, "clay_pct": 5.0,
        "texture": "sand", "drainage": "Very poorly drained", "map_unit": "Floridana fine sand",
    }


def test_get_soil_none_without_map_unit(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeClient({})
    monkeypatch.setattr(soil, "http", lambda: fake)

    assert soil.get_soil(25.0, -80.0) is None
    assert soil.get_soil(25.0, -80.0) is None
    assert fake.calls == 1


@pytest.mark.parametrize("sand,clay,om,expected", [
    (None, None, 35.0, "muck"),
    (94, 5, 5.0, "sand"),
    (83, 8, 1.2, "loamy sand"),
    (65, 12, None, "sandy loam"),
    (40, 20, None, "loam"),
    (20, 15, None, "silt loam"),
    (60, 25, None, "sandy clay loam"),
    (10, 60, None, "clay"),
    (None, 10, None, None),
])
def test_texture_class(sand: float | None, clay: float | None, om: float | None,
                       expected: str | None) -> None:
    assert soil.texture_class(sand, clay, om) == expected
