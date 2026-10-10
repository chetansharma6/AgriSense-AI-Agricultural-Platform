"""Fake HTTP client for tests: returns a canned JSON payload and counts calls."""

import json
from typing import Any


class FakeResponse:
    def __init__(self, payload: Any, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def raise_for_status(self) -> None:
        pass

    def json(self) -> Any:
        return self._payload


class FakeClient:
    def __init__(self, payload: Any, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code
        self.calls = 0

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls += 1
        return FakeResponse(self.payload, self.status_code)

    post = get
