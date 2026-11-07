"""The mapper is the heart of the app: wrong mapping = wrong weather for every user."""
from dataclasses import replace
from urllib.parse import parse_qs, urlparse

import pytest
import requests
from pydantic import BaseModel
from requests.exceptions import ConnectionError, HTTPError, Timeout

from tests.conftest import VC_CONFIG
from tests.helpers import make_vc_response
from wapp.services.third_party_apis.visual_crossing import (
    VisualCrossing,
    VisualCrossingResponseError,
    WeatherAppError,
    _check_map,
)


def provider(payload=None, **kwargs):
    """A VisualCrossing whose HTTP call returns `payload` and records what it was called with."""
    calls = []

    def fake_fetch(url, timeout):
        calls.append({"url": url, "timeout": timeout})
        return make_vc_response() if payload is None else payload

    return VisualCrossing(VC_CONFIG, fetch_json=fake_fetch, **kwargs), calls


def raising_provider(exc):
    def fake_fetch(url, timeout):
        raise exc

    return VisualCrossing(VC_CONFIG, fetch_json=fake_fetch)


# --- Construction ---------------------------------------------------------------

def test_missing_api_key_fails_at_construction():
    with pytest.raises(ValueError, match="API key"):
        VisualCrossing(replace(VC_CONFIG, api_key=""))


# --- Request --------------------------------------------------------------------

def test_url_has_location_and_all_query_params():
    vc, calls = provider()
    vc.fetch_map_data("10001")

    url = urlparse(calls[0]["url"])
    query = parse_qs(url.query)
    assert url.path == "/timeline/10001"
    assert query["key"] == ["test-key"]
    assert query["unitGroup"] == ["us"]
    assert query["include"] == ["hours,events,alerts"]
    assert query["contentType"] == ["json"]


def test_unit_group_argument_overrides_config_default():
    vc, calls = provider()
    vc.fetch_map_data("10001", unit_group="metric")

    assert parse_qs(urlparse(calls[0]["url"]).query)["unitGroup"] == ["metric"]


def test_configured_timeout_is_passed_to_http_call():
    vc, calls = provider(timeout=7)
    vc.fetch_map_data("10001")

    assert calls[0]["timeout"] == 7


def test_empty_zipcode_is_rejected():
    vc, _ = provider()
    with pytest.raises(ValueError):
        vc.fetch_map_data("")


# --- Mapping --------------------------------------------------------------------

def test_daily_fields_land_in_the_right_model_fields():
    """Every source value in the fixture is distinct, so any swap fails here."""
    vc, _ = provider()
    day = vc.fetch_map_data("10001").daily_forecast["2026-11-05"]

    t = day.temperature
    assert (t.max_temp, t.min_temp, t.temp, t.avg_temp) == (60.0, 40.0, 51.0, 50.0)
    assert (t.max_feels_like, t.min_feels_like, t.feels_like, t.dew_point) == (58.0, 38.0, 49.0, 35.0)

    c = day.conditions
    assert c.weather_icon == "rain"
    assert c.condits == "Rain, Partially cloudy"
    assert c.description == "Partly cloudy with rain."

    p = day.precipitation
    assert (p.precip, p.snowfall, p.snow_depth, p.precip_cover) == (0.1, 0.5, 0.2, 4.17)
    assert p.precip_type == ["rain"]

    w = day.wind_and_pressure
    assert (w.wind_speed, w.wind_gust, w.wind_direction, w.sea_level_pressure) == (10.0, 20.0, 200.0, 1012.0)

    h = day.humidity_and_clouds
    assert (h.relative_humidity, h.cloud_cover, h.visibility) == (55.0, 40.0, 9.5)

    assert (day.astronomy.sunrise, day.astronomy.sunset, day.astronomy.moon_phase) == ("06:30:00", "16:50:00", 0.5)
    assert (day.solar.solar_radiation, day.solar.uv_index) == (120.0, 4.0)
    assert day.severe_weather.severe_risk == 15
    assert day.source == "comb"


def test_avg_temp_is_none_for_hours_without_min_and_max():
    vc, _ = provider()
    hour = next(iter(vc.fetch_map_data("10001").hourly_forecast["2026-11-05"].values()))

    assert hour.temperature.avg_temp is None
    assert hour.temperature.max_temp is None


def test_forecast_is_keyed_by_date_then_hour_epoch():
    payload = make_vc_response()
    vc, _ = provider(payload)
    data = vc.fetch_map_data("10001")

    assert list(data.daily_forecast) == ["2026-11-05", "2026-11-06"]
    hours = data.hourly_forecast["2026-11-05"]
    assert len(hours) == 24
    first = payload["days"][0]["hours"][0]
    assert hours[str(first["datetimeEpoch"])].temperature.temp == first["temp"]


def test_dst_fall_back_day_keeps_all_25_hours():
    """Nov 1 2026 repeats 01:00 in New York. Keying by epoch must keep both."""
    vc, _ = provider(make_vc_response(start=__import__("datetime").date(2026, 11, 1), days=1))
    hours = vc.fetch_map_data("10001").hourly_forecast["2026-11-01"]

    assert len(hours) == 25


def test_location_info():
    vc, _ = provider(make_vc_response(zipcode="10001"))
    loc = vc.fetch_map_data("10001").location_info

    assert loc.time_zone == "America/New_York"
    assert (loc.latitude, loc.longitude) == (40.75, -73.99)


def test_zipcode_keeps_its_leading_zero():
    vc, _ = provider(make_vc_response(zipcode="02134"))

    assert vc.fetch_map_data("02134").location_info.zip_code == "02134"


# --- Errors ---------------------------------------------------------------------

def test_empty_response_raises_provider_error():
    vc, _ = provider(payload={})
    with pytest.raises(VisualCrossingResponseError):
        vc.fetch_map_data("10001")


@pytest.mark.parametrize("broken", [
    {"days": []},
    {"days": None},
    "no_hours",
])
def test_malformed_response_raises_internal_error(broken):
    payload = make_vc_response()
    if broken == "no_hours":
        payload["days"][0]["hours"] = []
    else:
        payload.update(broken)
    vc, _ = provider(payload)

    with pytest.raises(WeatherAppError):
        vc.fetch_map_data("10001")


def test_data_failing_model_validation_is_internal_not_client_error():
    """Pydantic errors are ValueErrors, which the controller turns into 400.
    Bad provider data is not the client's fault, so it must not be a ValueError."""
    payload = make_vc_response()
    payload["days"][0]["temp"] = "not-a-number"
    vc, _ = provider(payload)

    with pytest.raises(WeatherAppError) as exc_info:
        vc.fetch_map_data("10001")
    assert not isinstance(exc_info.value, ValueError)


def _http_error(status: int) -> HTTPError:
    response = requests.Response()
    response.status_code = status
    response._content = b"Bad API Request: Invalid location parameter value."
    return HTTPError(response=response)


@pytest.mark.parametrize("exc", [_http_error(400), _http_error(500), Timeout(), ConnectionError()])
def test_network_and_http_failures_become_provider_errors(exc):
    with pytest.raises(VisualCrossingResponseError):
        raising_provider(exc).fetch_map_data("10001")


# --- Startup map check ----------------------------------------------------------

class _Sample(BaseModel):
    a: int
    b: int = 0


def test_check_map_accepts_a_matching_map():
    _check_map(_Sample, {"a": "x", "b": "y"})


def test_check_map_rejects_unknown_field():
    with pytest.raises(TypeError, match="Unknown fields"):
        _check_map(_Sample, {"a": "x", "typo": "y"})


def test_check_map_rejects_missing_required_field():
    with pytest.raises(TypeError, match=r"Missing required fields: \['a'\]"):
        _check_map(_Sample, {"b": "y"})


def test_check_map_allows_computed_required_field():
    _check_map(_Sample, {"b": "y"}, frozenset({"a"}))
