from app.clients.nass import _safe_error


def test_nass_error_redacts_credential_shaped_values() -> None:
    message = _safe_error("invalid api_key=secret-value&format=JSON token=another-secret")
    assert "secret-value" not in message
    assert "another-secret" not in message
    assert "[redacted]" in message
