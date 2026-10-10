"""Climate summaries from NASA POWER daily weather."""

from dataclasses import dataclass
from datetime import date

import pandas as pd

FREEZE_C = 0.0


@dataclass
class SeasonStats:
    mean_temp_c: float
    freeze_days: float
    precip_mm: float
    months: float


def _parse_md(month_day: str) -> tuple[int, int]:
    month, day = month_day.split("-")
    return int(month), int(day)


def season_stats(weather: pd.DataFrame, start: str, end: str) -> SeasonStats | None:
    """Average a growing window over every complete season in the data."""
    start_m, start_d = _parse_md(start)
    end_m, end_d = _parse_md(end)
    crosses_year = (end_m, end_d) < (start_m, start_d)
    first, last = weather.index.min().date(), weather.index.max().date()

    temps, freezes, rains, lengths = [], [], [], []
    for year in range(first.year, last.year + 1):
        season_start = date(year, start_m, start_d)
        season_end = date(year + 1 if crosses_year else year, end_m, end_d)
        if season_start < first or season_end > last:
            continue
        days = weather.loc[str(season_start):str(season_end)]
        temps.append(days["t_mean_c"].mean())
        freezes.append(int((days["t_min_c"] <= FREEZE_C).sum()))
        rains.append(days["precip_mm"].sum())
        lengths.append(len(days))
    if not temps:
        return None
    return SeasonStats(
        mean_temp_c=float(pd.Series(temps).mean()),
        freeze_days=float(pd.Series(freezes).mean()),
        precip_mm=float(pd.Series(rains).mean()),
        months=float(pd.Series(lengths).mean()) / 30.44,
    )


def summarize(weather: pd.DataFrame) -> dict[str, float | int | str | None]:
    """Climate fields of the API 'conditions' object."""
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
        # Frost-free days lie strictly between the two freezes; a year with no
        # freeze at all counts as 365.
        after = last_spring if last_spring is not None else pd.Timestamp(year - 1, 12, 31)
        before = first_fall if first_fall is not None else pd.Timestamp(year + 1, 1, 1)
        frost_free.append(min(365, (before - after).days - 1))

    n_years = len(yearly_precip)
    summer = years[years.index.month.isin([6, 7, 8])]
    winter = years[years.index.month.isin([12, 1, 2])]
    return {
        "annual_precip_mm": round(float(yearly_precip.mean())),
        "frost_free_days": round(sum(frost_free) / n_years),
        "last_spring_frost": _typical_date(spring, n_years),
        "first_fall_frost": _typical_date(fall, n_years),
        "avg_summer_high_c": round(float(summer["t_max_c"].mean()), 1),
        "avg_winter_low_c": round(float(winter["t_min_c"].mean()), 1),
    }


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
