"""Climate summaries from NASA POWER daily weather.

NASA POWER is a ~50 km grid, so freeze counts and frost dates are
approximate for a specific farm: low-lying fields can freeze more often than
the grid cell average suggests.

Pure computation (DataFrame in, dict out) lives here; the HTTP call and its
cache are in app.clients.power. Run `python -m app.climate` from backend/ to
print the demo farms.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd

from app.clients.power import get_daily_weather

FREEZE_C = 0.0
# At or below -2 C (28 F) most crops take real damage (corn, snap bean, sugarcane buds);
# a night between -2 and 0 C mostly injures leaves.
HARD_FREEZE_C = -2.0
SOURCE = "NASA POWER"


@dataclass
class SeasonStats:
    mean_temp_c: float
    freeze_days: float  # nights at or below FREEZE_C, including hard freezes
    precip_mm: float
    months: float
    hard_freeze_days: float = 0.0  # nights at or below HARD_FREEZE_C


def _parse_md(month_day: str) -> tuple[int, int]:
    month, day = month_day.split("-")
    return int(month), int(day)


def with_station_minimums(weather: pd.DataFrame, station_min_c: pd.Series) -> pd.DataFrame:
    """Daily minimums from a nearby FAWN station, with NASA POWER filling station gaps.
    Only the minimum is replaced: it drives freeze counts, where the POWER grid is biased."""
    merged = weather.copy()
    merged["t_min_c"] = station_min_c.reindex(merged.index).combine_first(merged["t_min_c"])
    return merged


def season_stats(weather: pd.DataFrame, start: str, end: str) -> SeasonStats | None:
    """Average a growing window over every complete season in the data."""
    start_m, start_d = _parse_md(start)
    end_m, end_d = _parse_md(end)
    crosses_year = (end_m, end_d) < (start_m, start_d)
    first, last = weather.index.min().date(), weather.index.max().date()

    temps, freezes, hard_freezes, rains, lengths = [], [], [], [], []
    for year in range(first.year, last.year + 1):
        season_start = date(year, start_m, start_d)
        season_end = date(year + 1 if crosses_year else year, end_m, end_d)
        if season_start < first or season_end > last:
            continue
        days = weather.loc[str(season_start):str(season_end)]
        temps.append(days["t_mean_c"].mean())
        freezes.append(int((days["t_min_c"] <= FREEZE_C).sum()))
        hard_freezes.append(int((days["t_min_c"] <= HARD_FREEZE_C).sum()))
        rains.append(days["precip_mm"].sum())
        lengths.append(len(days))
    if not temps:
        return None
    return SeasonStats(
        mean_temp_c=float(pd.Series(temps).mean()),
        freeze_days=float(pd.Series(freezes).mean()),
        precip_mm=float(pd.Series(rains).mean()),
        months=float(pd.Series(lengths).mean()) / 30.44,
        hard_freeze_days=float(pd.Series(hard_freezes).mean()),
    )


def get_climate(lat: float, lon: float) -> dict[str, Any]:
    """Climate summary for a point (daily data is cached by the POWER client,
    so only the first call for a grid cell touches the network)."""
    return summarize(get_daily_weather(lat, lon))


def summarize(weather: pd.DataFrame) -> dict[str, Any]:
    """Monthly normals plus the climate fields of the API 'conditions' object."""
    years = weather[weather.index.year.isin(_complete_years(weather))]
    yearly_precip = years["precip_mm"].groupby(years.index.year).sum()

    spring, fall, frost_free = [], [], []
    for year, days in years.groupby(years.index.year):
        freezes = days.index[days["t_min_c"] <= FREEZE_C]
        spring_freezes = freezes[freezes.month < 7]
        fall_freezes = freezes[freezes.month >= 7]
        last_spring = spring_freezes.max() if len(spring_freezes) else None
        first_fall = fall_freezes.min() if len(fall_freezes) else None
        if last_spring is not None:
            spring.append(last_spring)
        if first_fall is not None:
            fall.append(first_fall)
        # Frost-free days lie strictly between the two freezes; with no spring
        # freeze the season starts Jan 1, with no fall freeze it ends Dec 31,
        # and a year with no freeze at all counts as 365.
        after = last_spring if last_spring is not None else pd.Timestamp(year - 1, 12, 31)
        before = first_fall if first_fall is not None else pd.Timestamp(year + 1, 1, 1)
        frost_free.append(min(365, (before - after).days - 1))

    summer = years[years.index.month.isin([6, 7, 8])]
    winter = years[years.index.month.isin([12, 1, 2])]
    return {
        "monthly": monthly_normals(years),
        "annual_precip_mm": _round(yearly_precip.mean()),
        "frost_free_days": _round(sum(frost_free) / len(frost_free)),
        "last_spring_frost": _typical_date(spring, len(frost_free)),
        "first_fall_frost": _typical_date(fall, len(frost_free)),
        "avg_summer_high_c": _round(summer["t_max_c"].mean()),
        "avg_winter_low_c": _round(winter["t_min_c"].mean()),
        "source": SOURCE,
    }


def monthly_normals(weather: pd.DataFrame) -> list[dict[str, Any]]:
    """One entry per month: mean temperatures, and the average monthly total
    of rain and of freeze days across years."""
    by_month_year = weather.groupby([weather.index.month, weather.index.year])
    totals = pd.DataFrame({
        "precip_mm": by_month_year["precip_mm"].sum(),
        "freeze_days": by_month_year["t_min_c"].apply(lambda t: int((t <= FREEZE_C).sum())),
    }).groupby(level=0).mean()
    means = weather.groupby(weather.index.month)[["t_max_c", "t_min_c", "t_mean_c"]].mean()
    return [
        {
            "month": int(month),
            "tmax_c": _round(means.loc[month, "t_max_c"]),
            "tmin_c": _round(means.loc[month, "t_min_c"]),
            "tmean_c": _round(means.loc[month, "t_mean_c"]),
            "precip_mm": _round(totals.loc[month, "precip_mm"]),
            "freeze_days": _round(totals.loc[month, "freeze_days"]),
        }
        for month in means.index
    ]


def _round(value: float) -> float | None:
    return None if pd.isna(value) else round(float(value), 1)


def _complete_years(weather: pd.DataFrame) -> list[int]:
    counts = weather.groupby(weather.index.year).size()
    return [int(year) for year, n in counts.items() if n >= 365]


def _typical_date(dates: list[pd.Timestamp], n_years: int) -> str | None:
    """Median MM-DD of frost dates, or None if frost occurs in under half the years."""
    if len(dates) * 2 < n_years:
        return None
    # Day of year relative to Jul 1 keeps Dec and Jan dates in order.
    offsets = sorted((d - pd.Timestamp(d.year, 7, 1)).days % 365 for d in dates)
    median = offsets[len(offsets) // 2]
    return (pd.Timestamp(2001, 7, 1) + pd.Timedelta(days=median)).strftime("%m-%d")


if __name__ == "__main__":
    import time

    from app.config import DEMO_FARMS

    started = time.perf_counter()
    for name, (lat, lon) in DEMO_FARMS.items():
        climate = get_climate(lat, lon)
        print(f"{name}:")
        for key, value in climate.items():
            if key != "monthly":
                print(f"  {key}: {value}")
        for month in climate["monthly"]:
            print(f"  {month}")
    print(f"elapsed: {time.perf_counter() - started:.2f} s")
