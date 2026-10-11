import math

import pytest

from app.clients import power
from tests.fakes import FakeClient

PARAMETER = {
    "T2M": {"20240101": 15.0, "20240102": -999.0},
    "T2M_MAX": {"20240101": 21.0, "20240102": 22.0},
    "T2M_MIN": {"20240101": 9.0, "20240102": 10.0},
    "PRECTOTCORR": {"20240101": 0.0, "20240102": 12.5},
}


@pytest.fixture(autouse=True)
def short_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(power, "START", "20240101")
    monkeypatch.setattr(power, "END", "20240102")


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


def test_retries_once_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    class FlakyClient(FakeClient):
        def get(self, url: str, **kwargs: object) -> object:
            self.calls += 1
            if self.calls == 1:
                raise httpx.ReadTimeout("slow")
            return super().get(url, **kwargs)

    fake = FlakyClient({"properties": {"parameter": PARAMETER}})
    monkeypatch.setattr(power, "http", lambda: fake)
    assert len(power.get_daily_weather(29.71, -81.50)) == 2
    assert fake.calls == 3  # FakeClient.get also counts the successful call


@pytest.mark.parametrize("payload", [{}, {"properties": {"parameter": {}}}, {"properties": {}}])
def test_empty_or_malformed_response_is_classified(monkeypatch: pytest.MonkeyPatch, payload: object) -> None:
    monkeypatch.setattr(power, "http", lambda: FakeClient(payload))
    with pytest.raises(power.PowerError):
        power.get_daily_weather(29.71, -81.50)


@pytest.mark.parametrize("corruption", ["missing_parameter", "missing_day", "wrong_day", "nonfinite", "text_value"])
def test_live_incomplete_or_invalid_weather_is_rejected(monkeypatch, corruption: str) -> None:
    import copy

    data = copy.deepcopy(PARAMETER)
    if corruption == "missing_parameter":
        del data["T2M_MIN"]
    elif corruption == "missing_day":
        del data["T2M_MIN"]["20240102"]
    elif corruption == "wrong_day":
        data["T2M_MIN"]["20241301"] = data["T2M_MIN"].pop("20240102")
    elif corruption == "nonfinite":
        data["T2M_MIN"]["20240102"] = float("inf")
    else:
        data["T2M_MIN"]["20240102"] = "bad"
    monkeypatch.setattr(power, "http", lambda: FakeClient({"properties": {"parameter": data}}))
    with pytest.raises(power.PowerError, match="malformed"):
        power.get_daily_weather(27.945, -82.4583)
