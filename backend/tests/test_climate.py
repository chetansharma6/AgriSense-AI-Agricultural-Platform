import pandas as pd

from app.climate import season_stats, summarize


def weather(t_min: float = 10.0, freeze_dates: tuple[str, ...] = ()) -> pd.DataFrame:
    days = pd.date_range("2021-01-01", "2023-12-31", freq="D")
    frame = pd.DataFrame(
        {"t_mean_c": 20.0, "t_max_c": 28.0, "t_min_c": t_min, "precip_mm": 3.0},
        index=days,
    )
    for day in freeze_dates:
        frame.loc[day, "t_min_c"] = -2.0
    return frame


def test_season_stats_window_crossing_new_year() -> None:
    stats = season_stats(weather(freeze_dates=("2022-01-10",)), "12-01", "01-31")
    assert stats is not None
    # Two complete seasons (Dec 2021-Jan 2022, Dec 2022-Jan 2023), 62 days each.
    assert stats.precip_mm == 3.0 * 62
    assert stats.freeze_days == 0.5
    assert round(stats.months, 1) == 2.0


def test_summarize_frost_free_year() -> None:
    summary = summarize(weather())
    assert summary["frost_free_days"] == 365
    assert summary["last_spring_frost"] is None
    assert summary["first_fall_frost"] is None
    assert summary["annual_precip_mm"] == round(3.0 * (365 * 3 + 0) / 3)


def test_summarize_frost_dates() -> None:
    freezes = ("2021-02-10", "2021-12-05", "2022-02-12", "2022-12-07", "2023-02-14", "2023-12-09")
    summary = summarize(weather(freeze_dates=freezes))
    assert summary["last_spring_frost"] == "02-12"
    assert summary["first_fall_frost"] == "12-07"
    assert 290 < summary["frost_free_days"] < 300


def test_jan_and_dec_freeze_gives_about_335_frost_free_days() -> None:
    freezes = ("2021-01-15", "2021-12-15", "2022-01-15", "2022-12-15", "2023-01-15", "2023-12-15")
    summary = summarize(weather(freeze_dates=freezes))
    assert summary["frost_free_days"] == 333.0  # Jan 16 to Dec 14
    assert summary["source"] == "NASA POWER"


def test_monthly_normals() -> None:
    summary = summarize(weather(freeze_dates=("2021-01-15", "2022-01-20")))
    monthly = summary["monthly"]
    assert [m["month"] for m in monthly] == list(range(1, 13))
    january = monthly[0]
    assert january["precip_mm"] == 93.0  # 31 days x 3 mm
    assert january["freeze_days"] == round(2 / 3, 1)
    assert january["tmax_c"] == 28.0
    assert monthly[1]["freeze_days"] == 0.0


def test_season_stats_counts_hard_freezes_separately() -> None:
    frame = weather()
    frame.loc["2022-01-05", "t_min_c"] = -0.5  # light freeze
    frame.loc["2022-01-06", "t_min_c"] = -2.0  # hard freeze, exactly on the threshold
    frame.loc["2022-01-07", "t_min_c"] = -6.0  # hard freeze
    stats = season_stats(frame, "01-01", "01-31")
    assert stats is not None
    # Three complete Januaries (2021-2023); only 2022 has freezes.
    assert stats.freeze_days == 1.0
    assert stats.hard_freeze_days == 2 / 3
