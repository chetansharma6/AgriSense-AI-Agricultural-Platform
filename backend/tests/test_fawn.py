from datetime import date

import pandas as pd

from app.clients import fawn


def test_parse_report_discards_incomplete_days() -> None:
    report = (
        '"FAWN Station","Period","2m T avg (F)","2m T min (F)","2m T max (F)","N (# obs)"\n'
        '"Hastings","25 Jan 2022","50.68","32.00","60.39","96"\n'
        '"Hastings","26 Jan 2022","54.30","40.00","58.91","89"\n'
    )

    result = fawn.parse_report(report)

    assert result == {date(2022, 1, 25): 0.0}


def test_nearest_station_uses_distance_limit(monkeypatch) -> None:
    station = {"id": "270", "name": "Hastings", "lat": 29.71, "lon": -81.50, "years": 10.0}
    monkeypatch.setattr(fawn, "load_stations", lambda: (station,))

    assert fawn.nearest_station(29.71, -81.50) == (station, 0.0)
    assert fawn.nearest_station(31.1, -87.7) is None


def test_daily_min_cache_round_trip(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(fawn, "read_cache", lambda namespace, params, validator=None: None)
    written = {}
    monkeypatch.setattr(fawn, "write_cache", lambda namespace, params, data: written.update(data))
    monkeypatch.setattr(fawn, "_download", lambda station_id: {date(2016, 1, 1): -2.5})

    result = fawn.daily_min_c("270")

    assert result.index[0] == pd.Timestamp("2016-01-01")
    assert result.loc["2016-01-01"] == -2.5
    assert written["min_c"][0] == -2.5
