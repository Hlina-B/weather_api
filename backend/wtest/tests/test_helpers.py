"""time_handler and http_request_helper: small, but the current-hour lookup depends on them."""
import pytest
from requests.exceptions import HTTPError

from wapp.services.helper import http_request_helper, time_handler


# --- time_handler ---------------------------------------------------------------

@pytest.mark.parametrize("now, expected", [
    (1_762_369_200.0, "1762369200"),  # exactly on the hour
    (1_762_369_201.5, "1762369200"),  # just after
    (1_762_372_799.9, "1762369200"),  # last second of the hour
])
def test_current_hour_start_epoch_floors_to_the_hour(monkeypatch, now, expected):
    monkeypatch.setattr(time_handler, "time", lambda: now)

    assert time_handler.current_hour_start_epoch() == expected


# --- http_request_helper --------------------------------------------------------

class _FakeResponse:
    def __init__(self, payload=None, error=None):
        self._payload, self._error = payload, error

    def raise_for_status(self):
        if self._error:
            raise self._error

    def json(self):
        return self._payload


def test_http_request_returns_json_and_sends_timeout_and_accept_header(monkeypatch):
    seen = {}

    def fake_get(url, headers, timeout):
        seen.update(url=url, headers=headers, timeout=timeout)
        return _FakeResponse(payload={"ok": True})

    monkeypatch.setattr(http_request_helper.requests, "get", fake_get)

    assert http_request_helper.http_request("https://x", 3) == {"ok": True}
    assert seen["timeout"] == 3
    assert seen["headers"] == {"Accept": "application/json"}


def test_http_request_raises_on_error_status(monkeypatch):
    monkeypatch.setattr(
        http_request_helper.requests, "get",
        lambda url, headers, timeout: _FakeResponse(error=HTTPError("400")),
    )

    with pytest.raises(HTTPError):
        http_request_helper.http_request("https://x")
