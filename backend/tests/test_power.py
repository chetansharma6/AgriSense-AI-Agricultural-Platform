import math

import pytest

from app.clients import power
from tests.fakes import FakeClient

PARAMETER = {
    "T2M": {"20240101": 15.0, "20240102": -999.0},
    "T2M_MAX": {"20240101": 21.0, "20240102": 22.0},
    "T2M_MIN": {"20240101": 9.0, "20240102": 10.0},
    "PRECTOTCORR": {"20240101": 0.0, "20240102": 12.5},
    "ALLSKY_SFC_SW_DWN": {"20240101": 3.1, "20240102": 2.4},
}


def test_daily_weather_frame_and_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeClient({"properties": {"parameter": PARAMETER}})
    monkeypatch.setattr(power, "http", lambda: fake)

    frame = power.get_daily_weather(29.71, -81.50)
    assert list(frame.columns) == list(power.PARAMETERS.values())
    assert str(frame.index[0].date()) == "2024-01-01"
    assert frame.loc["2024-01-02", "precip_mm"] == 12.5
    assert math.isnan(frame.loc["2024-01-02", "t_mean_c"])

    power.get_daily_weather(29.74, -81.53)  # rounds to the same 0.1 degree cell
    assert fake.calls == 1
