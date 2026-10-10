"""NASS CSV export: which rows are kept and how they are written (no network)."""

from scripts.export_nass import FL_COUNTIES, records, series_by_desc

from app.crops import load_crops

SERIES = series_by_desc(load_crops().values())
POTATO_YIELD = "POTATOES - YIELD, MEASURED IN CWT / ACRE"


def row(short_desc: str, value: str, year: int = 2022, period: str = "YEAR", domain: str = "TOTAL",
        **extra: str) -> dict[str, str]:
    return {"short_desc": short_desc, "Value": value, "year": str(year), "reference_period_desc": period,
            "domain_desc": domain, "statisticcat_desc": "YIELD", **extra}


def test_florida_county_codes() -> None:
    assert len(FL_COUNTIES) == 67
    assert "086" in FL_COUNTIES and "025" not in FL_COUNTIES  # Miami-Dade's current code


def test_series_cover_every_crop() -> None:
    kinds = {(crop_id, kind) for crop_id, kind in SERIES.values()}
    assert {crop_id for crop_id, _ in kinds} == set(load_crops())
    assert {kind for _, kind in kinds} == {"yield", "price", "acres"}


def test_yield_records_keep_annual_rows_and_parse_values() -> None:
    rows = [
        row(POTATO_YIELD, "290", county_name="ST. JOHNS"),
        row(POTATO_YIELD, "(D)", year=2023),
        row(POTATO_YIELD, "300", period="MAR"),  # not annual: dropped, as in the app
        row("POTATOES - PRICE RECEIVED, MEASURED IN $ / CWT", "18", period="MARKETING YEAR"),  # a price, not a yield
        row("BEETS - YIELD, MEASURED IN CWT / ACRE", "10"),  # not one of our crops
    ]
    out = records(rows, SERIES, "yield", "county", "109")
    assert [(r["crop_id"], r["year"], r["value"], r["value_raw"]) for r in out] == [
        ("potato", 2022, 290.0, "290"), ("potato", 2023, "", "(D)")]
    assert out[0]["county_fips"] == "12109" and out[0]["county_name"] == "St. Johns"
    assert out[0]["unit"] == "CWT / ACRE"


def test_acres_records_keep_total_domain_only() -> None:
    rows = [row("PEANUTS - ACRES HARVESTED", "3,900"),
            row("PEANUTS - ACRES HARVESTED", "100", domain="AREA HARVESTED")]
    out = records(rows, SERIES, "acres", "county", "063")
    assert [(r["crop_id"], r["value"], r["unit"]) for r in out] == [("peanut", 3900.0, "ACRES")]


def test_state_records_have_no_county() -> None:
    out = records([row(POTATO_YIELD, "280")], SERIES, "yield", "state")
    assert out[0]["level"] == "state" and out[0]["county_fips"] == ""
