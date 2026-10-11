from app.crops import load_crops
from app.market import Market, average_yield, county_acreage, price_range

POTATO = load_crops()["potato"]
YIELD = "POTATOES - YIELD, MEASURED IN CWT / ACRE"
PRICE = "POTATOES - PRICE RECEIVED, MEASURED IN $ / CWT"


def row(short_desc: str, year: int, value: str, period: str = "YEAR") -> dict:
    return {"short_desc": short_desc, "year": str(year), "Value": value,
            "reference_period_desc": period, "domain_desc": "TOTAL"}


def test_yield_prefers_county_and_uses_recent_years() -> None:
    state = [row(YIELD, year, "100") for year in range(2015, 2025)]
    county = [row(YIELD, 2023, "300"), row(YIELD, 2024, "(D)")]
    market = Market(county_rows=[], state_rows=state, county_yield_rows=county)
    assert average_yield(market, POTATO) == {"value": 300.0, "unit": "CWT / ACRE", "level": "county"}

    market = Market(county_rows=[], state_rows=state, county_yield_rows=[])
    assert average_yield(market, POTATO)["level"] == "state"


def test_price_range_last_five_years() -> None:
    values = ["10", "12", "1,050", "14.5", "22", "18", "(D)"]
    state = [row(PRICE, 2018 + i, v, "MARKETING YEAR") for i, v in enumerate(values)]
    market = Market(county_rows=[], state_rows=state, county_yield_rows=[])
    assert price_range(market, POTATO) == {"low": 12.0, "high": 1050.0, "unit": "$ / CWT"}


def test_county_acreage_latest_census() -> None:
    acres = POTATO.nass.acres_descs[0]
    market = Market(
        county_rows=[row(acres, 2017, "8,426"), row(acres, 2022, "4,197"),
                     row("POTATOES, FRESH MARKET - ACRES HARVESTED", 2022, "(D)")],
        state_rows=[], county_yield_rows=[],
    )
    acreage = county_acreage(market, POTATO)
    assert (acreage.year, acreage.acres) == (2022, 4197.0)

    assert county_acreage(Market(None, [], []), POTATO) is None
    assert not county_acreage(Market([], [], []), POTATO).grown


def test_load_market_runs_all_queries(monkeypatch) -> None:
    from app import market as market_module
    from app import config

    monkeypatch.setattr(config, "NASS_USE_SNAPSHOT", False)

    seen = []

    def fake_query(params: dict, invalid_means_empty: bool = False) -> list[dict]:
        seen.append((params.get("county_ansi"), params["statisticcat_desc"]))
        return [row(POTATO.nass.acres_descs[0], 2022, "10")] if params.get("county_ansi") else []

    monkeypatch.setattr(market_module.nass, "query", fake_query)
    market = market_module.load_market("12109")
    assert sorted(seen, key=str) == sorted([
        (None, "YIELD"), (None, "PRICE RECEIVED"),
        ("109", "AREA HARVESTED"), ("109", "AREA BEARING"), ("109", "YIELD"),
    ], key=str)
    assert len(market.county_rows) == 2

    assert market_module.load_market(None).county_rows is None


def test_snapshot_market_is_complete_without_api_requests(monkeypatch) -> None:
    from app import config, market as market_module

    monkeypatch.setattr(config, "NASS_USE_SNAPSHOT", True)
    monkeypatch.setattr(market_module.nass, "query", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("network")))
    market = market_module.load_market("12109")
    assert market.source == "snapshot"
    assert market.data_period.startswith("2012-")
    assert county_acreage(market, POTATO).grown
    assert average_yield(market, POTATO)["value"] > 0
    assert price_range(market, POTATO)["low"] > 0
    assert market_module.load_market(None).county_rows is None


def test_missing_snapshot_falls_back_to_live_market(monkeypatch, tmp_path) -> None:
    from app import config, market as market_module

    monkeypatch.setattr(config, "NASS_USE_SNAPSHOT", True)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(market_module.nass, "query", lambda *_args, **_kwargs: [])
    assert market_module.load_market("12109").source == "live"


def test_prices_rounded_to_cents() -> None:
    state = [row(PRICE, 2020, "0.232", "MARKETING YEAR"), row(PRICE, 2021, "0.2734", "MARKETING YEAR")]
    market = Market(county_rows=[], state_rows=state, county_yield_rows=[])
    assert price_range(market, POTATO) == {"low": 0.23, "high": 0.27, "unit": "$ / CWT"}
