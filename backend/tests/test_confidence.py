from app import service
from app.schemas import Confidence


FACTORS = ("soil_ph", "drainage", "season_temp", "frost_risk", "rainfall", "local_history")


def crop(factors: dict[str, int | None], history: str | None = "140 acres in county") -> dict:
    return {
        "factors": factors,
        "factor_details": {"local_history": {"value": history}},
    }


def test_complete_live_confidence() -> None:
    response = {"crops": [crop(dict.fromkeys(FACTORS, 100))],
                "warnings": [], "provenance": {"mode": "live"}}
    confidence = Confidence.model_validate(service._confidence(response))
    assert confidence.data_status == "live"
    assert confidence.available_factor_names == list(FACTORS)
    assert confidence.missing_factor_names == []
    assert confidence.county_history_status == "available"
    assert confidence.partial is False


def test_partial_failed_source_lists_missing_factor() -> None:
    factors = {name: 100 for name in FACTORS}
    factors["weather"] = None
    factors["season_temp"] = None
    response = {"crops": [crop(factors, None)],
                "warnings": ["NASA POWER unavailable (ConnectError); related values are null"],
                "provenance": {"mode": "live"}}
    confidence = service._confidence(response)
    assert confidence["data_status"] == "live"
    assert confidence["missing_factor_names"] == ["season_temp"]
    assert confidence["county_history_status"] == "absent"
    assert confidence["partial"] is True
    assert "ConnectError" not in " ".join(confidence["notes"])


def test_demo_and_cached_statuses_are_explicit() -> None:
    response = {"crops": [crop(dict.fromkeys(FACTORS, 100), "Grown in county (acreage withheld)" )],
                "warnings": [], "provenance": {"mode": "demo"}}
    assert service._confidence(response, "demo")["data_status"] == "demo"
    assert service._confidence(response, "cached")["data_status"] == "cached"
    assert service._confidence(response, "demo")["county_history_status"] == "withheld"
