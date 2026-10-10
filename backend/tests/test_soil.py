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


def test_no_map_unit_raises_and_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    client = use(monkeypatch, ScriptedClient(FakeResponse({})))
    for _ in range(2):
        with pytest.raises(soil.SoilNotFound):
            soil.get_soil(25.0, -80.0)
    assert client.calls == 1


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
