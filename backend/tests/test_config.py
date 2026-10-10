from fastapi.middleware.cors import CORSMiddleware

from app import config, main


def test_production_cors_has_no_wildcard_or_regex() -> None:
    assert config.CORS_ORIGIN_REGEX is None
    assert "*" not in config.CORS_ORIGINS
    cors = next(m for m in main.app.user_middleware if m.cls is CORSMiddleware)
    assert cors.kwargs["allow_credentials"] is False


def test_missing_environment_values_are_safe(monkeypatch) -> None:
    monkeypatch.delenv("NASS_API_KEY", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.setattr(config, "NASS_API_KEY", "")
    monkeypatch.setattr(config, "CORS_ORIGINS", ["http://localhost:3000"])
    assert config.CORS_ORIGINS == ["http://localhost:3000"]
    try:
        config.nass_api_key()
    except RuntimeError as error:
        assert "NASS_API_KEY" in str(error)
    else:
        raise AssertionError("missing NASS_API_KEY must fail safely")


def test_origin_parser_discards_wildcards_and_malformed_values() -> None:
    assert config._explicit_origins("*, https://*.vercel.app, javascript:bad, https://app.example.com/") == [
        "https://app.example.com"
    ]
