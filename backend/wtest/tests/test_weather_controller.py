"""HTTP layer: input validation, status codes, and the dev-only clear endpoint.
The service is replaced with a stub, so these tests only exercise the controller."""
from dataclasses import replace

import pytest

from tests.helpers import FakeStrategy
from wapp.controller import weather_controller as controller
from wapp.services.third_party_apis.visual_crossing import VisualCrossingResponseError, WeatherAppError


class ServiceStub:
    def __init__(self):
        self.get_calls, self.clear_calls = [], []
        self.error = None

    def get_weather_data(self, zipcode, unit_group):
        self.get_calls.append((zipcode, unit_group))
        if self.error:
            raise self.error
        return FakeStrategy().fetch_map_data(zipcode)

    def clear_weather_data(self, zipcode, unit_group):
        self.clear_calls.append((zipcode, unit_group))


@pytest.fixture
def stub(monkeypatch):
    stub = ServiceStub()
    monkeypatch.setattr(controller, "service", stub)
    return stub


@pytest.fixture
def client(stub):
    controller.limiter.reset()  # rate-limit counters must not leak between tests
    return controller.app.test_client()


# --- GET /weather: validation ---------------------------------------------------

@pytest.mark.parametrize("zipcode", [None, "", "1234", "123456", "abcde", "12a45", " 1234"])
def test_invalid_zipcode_is_400(client, stub, zipcode):
    params = {"unit_group": "us"}
    if zipcode is not None:
        params["zipcode"] = zipcode

    response = client.get("/weather", query_string=params)

    assert response.status_code == 400
    assert "error" in response.get_json()
    assert stub.get_calls == []


@pytest.mark.parametrize("unit_group", [None, "", "   ", "kelvin", "US"])
def test_invalid_unit_group_is_400(client, stub, unit_group):
    params = {"zipcode": "10001"}
    if unit_group is not None:
        params["unit_group"] = unit_group

    response = client.get("/weather", query_string=params)

    assert response.status_code == 400
    assert stub.get_calls == []


@pytest.mark.parametrize("unit_group", ["us", "metric", "uk", "base"])
def test_every_supported_unit_group_is_accepted(client, stub, unit_group):
    response = client.get("/weather", query_string={"zipcode": "10001", "unit_group": unit_group})

    assert response.status_code == 200
    assert stub.get_calls == [("10001", unit_group)]


def test_leading_zero_zipcode_reaches_service_as_string(client, stub):
    client.get("/weather", query_string={"zipcode": "02134", "unit_group": "us"})

    assert stub.get_calls == [("02134", "us")]


# --- GET /weather: responses ----------------------------------------------------

def test_success_returns_200_with_forecast(client, stub):
    response = client.get("/weather", query_string={"zipcode": "10001", "unit_group": "us"})

    body = response.get_json()
    assert response.status_code == 200
    assert set(body) == {"current_snapshot", "hourly_forecast", "daily_forecast", "location_info", "info"}
    assert body["daily_forecast"]["2026-11-05"]["temperature"]["temp"] == 51.0


@pytest.mark.parametrize("error, status", [
    (ValueError("No weather data found"), 400),
    (WeatherAppError("mapping failed"), 500),
    (VisualCrossingResponseError("timed out"), 500),
    (Exception("anything else"), 500),
])
def test_service_errors_map_to_status_codes(client, stub, error, status):
    stub.error = error

    response = client.get("/weather", query_string={"zipcode": "10001", "unit_group": "us"})

    assert response.status_code == status
    assert "error" in response.get_json()


# --- DELETE /weather/clear ------------------------------------------------------

def test_clear_works_in_dev(client, stub):
    response = client.delete("/weather/clear", query_string={"zipcode": "10001", "unit_group": "us"})

    assert response.status_code == 200
    assert stub.clear_calls == [("10001", "us")]


def test_clear_is_refused_outside_dev(client, stub, monkeypatch):
    monkeypatch.setattr(controller, "config", replace(controller.config, cache_clear_token="prod-secret"))

    response = client.delete("/weather/clear", query_string={"zipcode": "10001", "unit_group": "us"})

    assert response.status_code in (401, 403)
    assert response.is_json
    assert stub.clear_calls == []


@pytest.mark.parametrize("zipcode", [None, "1234", "abcde"])
def test_clear_rejects_invalid_zipcode(client, stub, zipcode):
    params = {"unit_group": "us"} if zipcode is None else {"zipcode": zipcode, "unit_group": "us"}

    response = client.delete("/weather/clear", query_string=params)

    assert response.status_code == 400
    assert stub.clear_calls == []


def test_clear_is_rate_limited(client, stub):
    params = {"zipcode": "10001", "unit_group": "us"}
    statuses = [client.delete("/weather/clear", query_string=params).status_code for _ in range(61)]

    assert statuses[:60] == [200] * 60
    assert statuses[60] == 429
