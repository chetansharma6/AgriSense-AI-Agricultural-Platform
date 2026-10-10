import pytest
import httpx

from app.clients import fcc
from tests.fakes import FakeClient

PAYLOAD = {"results": [{"county_name": "St. Johns County", "county_fips": "12109", "state_code": "FL"}]}


def test_lookup_county_strips_suffix_and_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeClient(PAYLOAD)
    monkeypatch.setattr(fcc, "http", lambda: fake)

    expected = {"county": "St. Johns", "county_fips": "12109", "state": "FL"}
    assert fcc.lookup_county(29.71, -81.50) == expected
    assert fcc.lookup_county(29.71, -81.50) == expected
    assert fake.calls == 1


def test_lookup_county_none_offshore(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeClient({"results": []})
    monkeypatch.setattr(fcc, "http", lambda: fake)

    assert fcc.lookup_county(25.0, -80.0) is None
    assert fcc.lookup_county(25.0, -80.0) is None
    assert fake.calls == 1


def test_malformed_response_is_classified(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeClient({"results": {"unexpected": "shape"}})
    monkeypatch.setattr(fcc, "http", lambda: fake)

    with pytest.raises(fcc.FccError, match="FCC response unavailable"):
        fcc.lookup_county(29.71, -81.50)


def test_missing_county_fields_are_classified(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeClient({"results": [{"county_name": "St. Johns County"}]})
    monkeypatch.setattr(fcc, "http", lambda: fake)

    with pytest.raises(fcc.FccError, match="FCC response malformed"):
        fcc.lookup_county(29.71, -81.50)


def test_timeout_is_classified(monkeypatch: pytest.MonkeyPatch) -> None:
    class TimeoutClient:
        def get(self, url: str, **kwargs: object) -> object:
            raise httpx.ReadTimeout("slow")

    monkeypatch.setattr(fcc, "http", lambda: TimeoutClient())
    with pytest.raises(fcc.FccTimeout):
        fcc.lookup_county(29.71, -81.50)
