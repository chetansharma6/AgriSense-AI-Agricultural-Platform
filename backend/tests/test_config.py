import pytest

from app.config import in_florida

DEMO_FARMS = [(30.80, -85.25), (29.71, -81.50), (28.03, -82.15), (26.68, -80.68)]


@pytest.mark.parametrize("lat,lon", DEMO_FARMS)
def test_demo_farms_are_in_florida(lat: float, lon: float) -> None:
    assert in_florida(lat, lon)


@pytest.mark.parametrize("lat,lon", [(33.75, -84.39), (24.0, -81.0), (28.0, -78.0)])
def test_outside_florida(lat: float, lon: float) -> None:
    assert not in_florida(lat, lon)
