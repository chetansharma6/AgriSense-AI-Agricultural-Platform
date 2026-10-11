"""Reproducible cold/cache checks. Controlled mode makes no network requests.

Run from backend/: python -m scripts.benchmark_backend
Use --mode live for a real Tampa request with an empty temporary disk cache.
Controlled timings model provider latency, not production network performance.
"""

import argparse
import csv
import json
import logging
import statistics
import tempfile
import time
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from app import cache, config, service
from app.clients import nass, power
from app.schemas import RecommendResponse


def delayed(value: object, seconds: float):
    def fetch(*args, **kwargs):
        time.sleep(seconds)
        return value
    return fetch


def controlled_providers(stack: ExitStack) -> None:
    days = pd.date_range("2016-01-01", "2025-12-31")
    weather = pd.DataFrame({"t_mean_c": 22., "t_max_c": 28., "t_min_c": 15., "precip_mm": 3.}, index=days)
    county = {"county": "Hillsborough", "county_fips": "12057", "state": "FL"}
    soil = {"soil_ph": 6.2, "organic_matter_pct": 1., "sand_pct": 94., "clay_pct": 3.,
            "texture": "sand", "drainage": "Well drained", "source": "controlled fixture"}
    stack.enter_context(patch.object(service, "lookup_county", delayed(county, .05)))
    stack.enter_context(patch.object(service, "get_soil", delayed(soil, .2)))
    stack.enter_context(patch.object(service, "get_daily_weather", delayed(weather, .2)))
    stack.enter_context(patch.object(service.fawn, "nearest_station", return_value=None))
    rows = []
    for path in (config.DATA_DIR / "processed").glob("nass_*.csv"):
        with path.open(newline="") as file:
            for row in csv.DictReader(file):
                rows.append({"short_desc": row["short_desc"], "year": row["year"], "Value": row["value_raw"],
                             "statisticcat_desc": row["statistic"], "domain_desc": "TOTAL",
                             "county_fips": row["county_fips"], "agg_level_desc": row["level"].upper(),
                             "reference_period_desc": "MARKETING YEAR" if row["statistic"] == "PRICE RECEIVED" else "YEAR"})

    def query(params, **kwargs):
        time.sleep(.2)
        return [row for row in rows if row["statisticcat_desc"] == params["statisticcat_desc"]
                and row["agg_level_desc"] == params["agg_level_desc"]
                and ("county_ansi" not in params or row["county_fips"] == "12" + params["county_ansi"])]

    stack.enter_context(patch.object(nass, "query", query))


def run(mode: str, samples: int) -> dict:
    cold, memory = [], []
    with ExitStack() as stack:
        stack.enter_context(patch.object(config, "DEMO_MODE", False))
        if mode == "controlled":
            controlled_providers(stack)
        for _ in range(samples):
            # Both response and per-provider caches start empty each time.
            with tempfile.TemporaryDirectory(prefix="agrisense-benchmark-") as directory:
                with patch.object(cache, "CACHE_DIR", Path(directory)):
                    service.clear_response_cache()
                    start = time.perf_counter()
                    result = service.recommend(27.9449854, -82.4583107)
                    cold.append(time.perf_counter() - start)
                    RecommendResponse.model_validate(result)
                    start = time.perf_counter()
                    repeated = service.recommend(27.9449854, -82.4583107)
                    memory.append(time.perf_counter() - start)
                    assert [crop["score"] for crop in result["crops"]] == [crop["score"] for crop in repeated["crops"]]
                    assert len(result["crops"]) == 13
    return {"mode": mode, "samples": samples,
            "cold_median_s": round(statistics.median(cold), 4), "cold_samples_s": [round(t, 4) for t in cold],
            "repeat_median_s": round(statistics.median(memory), 4),
            "soil_ph": result["conditions"]["soil_ph"], "drainage": result["conditions"]["drainage"],
            "warnings": result["warnings"], "provenance": result["provenance"]}


def validation_timing() -> dict:
    dates = pd.date_range("2016-01-01", "2025-12-31").strftime("%Y%m%d")
    payload = {parameter: dict.fromkeys(dates, 22.) for parameter in power.PARAMETERS}
    timings = []
    for _ in range(5):
        start = time.perf_counter()
        assert power._valid_series(payload)
        timings.append(time.perf_counter() - start)
    return {"power_validation_median_ms": round(statistics.median(timings) * 1000, 2)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("controlled", "live"), default="controlled")
    parser.add_argument("--samples", type=int, default=3)
    options = parser.parse_args()
    if not 1 <= options.samples <= 10:
        parser.error("samples must be between 1 and 10")
    logging.disable(logging.INFO)
    try:
        print(json.dumps({**run(options.mode, options.samples), **validation_timing()}, indent=2))
    finally:
        service._provider_pool.shutdown(wait=True)
