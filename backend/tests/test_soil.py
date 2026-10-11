"""get_soil and sda_query with the network faked."""

from typing import Any

import httpx
import pytest

from app.clients import soil
from tests.fakes import FakeResponse

MUKEY = {"Table": [["mukey"], ["1392058"]]}
HORIZONS = {"Table": [
    ["cokey", "compname", "comppct_r", "drainagecl", "majcompflag",
     "hzdept_r", "hzdepb_r", "ph1to1h2o_r", "om_r", "sandtotal_r", "claytotal_r"],
    ["1", "Floridana", "90", "Very poorly drained", "Yes", "0", "30", "5.8", "5", "94", "5"],
]}


class ScriptedClient:
    """Returns the given responses in order (an exception is raised)."""

    def __init__(self, *responses: Any) -> None:
        self.responses = list(responses)
        self.calls = 0

    def post(self, url: str, **kwargs: Any) -> Any:
        self.calls += 1
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def use(monkeypatch: pytest.MonkeyPatch, client: ScriptedClient) -> ScriptedClient:
    monkeypatch.setattr(soil, "http", lambda: client)
    return client


def test_get_soil_and_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    client = use(monkeypatch, ScriptedClient(FakeResponse(MUKEY), FakeResponse(HORIZONS)))
    result = soil.get_soil(29.71, -81.50)
    assert result["mukey"] == "1392058"
    assert result["soil_ph"] == 5.8
    assert result["texture"] == "sand"
    assert soil.get_soil(29.71, -81.50) == result
    assert client.calls == 2


def test_no_map_unit_raises_and_is_not_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    client = use(monkeypatch, ScriptedClient(*(FakeResponse({}) for _ in range(4))))
    for _ in range(2):
        with pytest.raises(soil.SoilNotFound):
            soil.get_soil(25.0, -80.0)
    assert client.calls == 4


def test_nearby_soil_fills_unmapped_urban_point(monkeypatch: pytest.MonkeyPatch) -> None:
    nearby = {"Table": [["candidate", "mukey"], ["0", "1392058"]]}
    horizons = {"Table": [
        ["mukey", *HORIZONS["Table"][0]],
        ["1392058", *HORIZONS["Table"][1]],
    ]}
    client = use(monkeypatch, ScriptedClient(FakeResponse({}), FakeResponse(nearby), FakeResponse(horizons)))
    result = soil.get_soil(27.9506, -82.4572)
    assert result["soil_ph"] == 5.8
    assert result["drainage"] == "Very poorly drained"
    assert "nearby survey" in result["source"]
    assert client.calls == 3


def test_nearby_failure_preserves_valid_on_site_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    partial = {"Table": [HORIZONS["Table"][0], [*HORIZONS["Table"][1]]]}
    partial["Table"][1][7] = None
    use(monkeypatch, ScriptedClient(FakeResponse(MUKEY), FakeResponse(partial)))
    monkeypatch.setattr(soil, "_nearby_soil", lambda *_args, **_kwargs: (_ for _ in ()).throw(httpx.ReadTimeout("slow")))
    writes = []
    monkeypatch.setattr(soil, "write_cache", lambda *_args: writes.append(1))
    result = soil.get_soil(27.945, -82.4583)
    assert result["soil_ph"] is None
    assert result["drainage"] == "Very poorly drained"
    assert result["sand_pct"] == 94.0
    assert not writes  # Retry optional enrichment after a temporary failure.


def test_partial_cache_does_not_bypass_nearby_enrichment(monkeypatch) -> None:
    cached = {"soil_ph": None, "organic_matter_pct": 1., "sand_pct": 94., "clay_pct": 3.,
              "texture": "sand", "drainage": "Well drained", "mukey": "123", "source": soil.SOURCE}
    nearby = {**cached, "soil_ph": 6.2, "source": soil.SOURCE + " (nearby survey, about 1.5 km away)"}
    monkeypatch.setattr(soil, "read_cache", lambda *_: cached)
    monkeypatch.setattr(soil, "get_mukey", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Refetched cached soil")))
    monkeypatch.setattr(soil, "_nearby_soil", lambda *_args, **_kwargs: nearby)
    result = soil.get_soil(27.945, -82.4583)
    assert result["soil_ph"] == 6.2
    assert "nearby survey" in result["source"]


@pytest.mark.parametrize("mukey", ["1' OR '1'='1", "１２３", "bad", ""])
def test_upstream_map_unit_keys_cannot_become_sql(monkeypatch, mukey) -> None:
    payload = {"Table": [["mukey"], [mukey]]}
    client = use(monkeypatch, ScriptedClient(FakeResponse(payload)))
    with pytest.raises(soil.SoilMalformed):
        soil.get_soil(27.945, -82.4583)
    assert client.calls == 1  # No horizon query may contain the untrusted key.


@pytest.mark.parametrize("candidate", ["-1", "100", "not-a-number"])
def test_nearby_candidate_indices_are_checked(monkeypatch, candidate) -> None:
    payload = {"Table": [["candidate", "mukey"], [candidate, "1392058"]]}
    use(monkeypatch, ScriptedClient(FakeResponse(payload)))
    with pytest.raises(soil.SoilMalformed):
        soil._nearby_soil(27.945, -82.4583, deadline=None)


def test_retries_once_on_timeout_and_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, ScriptedClient(httpx.ReadTimeout("slow"), FakeResponse(MUKEY)))
    assert soil.get_mukey(29.71, -81.50) == "1392058"

    use(monkeypatch, ScriptedClient(FakeResponse({}, status_code=503), FakeResponse(MUKEY)))
    assert soil.get_mukey(29.71, -81.50) == "1392058"


def test_second_timeout_is_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, ScriptedClient(httpx.ReadTimeout("slow"), httpx.ReadTimeout("slow")))
    with pytest.raises(httpx.ReadTimeout):
        soil.get_mukey(29.71, -81.50)


def test_maintenance_page_raises_and_is_not_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    page = FakeResponse({})
    page.text = "<html><body>Site is under daily maintenance</body></html>"
    client = use(monkeypatch, ScriptedClient(page, page))
    for _ in range(2):
        with pytest.raises(soil.SoilServiceDown):
            soil.get_soil(29.65, -82.32)
    assert client.calls == 2


def test_malformed_json_is_classified(monkeypatch: pytest.MonkeyPatch) -> None:
    class Malformed(FakeResponse):
        def json(self) -> Any:
            raise ValueError("not json")

    client = use(monkeypatch, ScriptedClient(Malformed({}), Malformed({})))
    with pytest.raises(soil.SoilMalformed):
        soil.get_mukey(29.71, -81.50)
    assert client.calls == 1
