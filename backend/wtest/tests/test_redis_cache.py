"""The cache must return exactly what was stored, under the right key, for a limited time."""
import pytest

from tests.helpers import FakeStrategy
from wapp.models.weather_models import AggWeatherData, Temperature, WeatherData
from wapp.services.cache import redis_cache

KEY = "test_agg_weather_data"


@pytest.fixture
def data():
    return FakeStrategy().fetch_map_data("10001")


def test_miss_returns_none(fake_redis):
    assert redis_cache.get_agg_weather_data("10001", "us") is None


def test_cache_hit_returns_the_same_nested_models_as_a_miss(fake_redis, data):
    """Before pydantic, a hit returned plain dicts below the top level."""
    redis_cache.set_agg_weather_data(data, "10001", "us")
    cached = redis_cache.get_agg_weather_data("10001", "us")

    assert isinstance(cached, AggWeatherData)
    day = cached.daily_forecast["2026-11-05"]
    assert isinstance(day, WeatherData)
    assert isinstance(day.temperature, Temperature)
    assert cached == data


def test_entries_expire_after_the_configured_ttl(fake_redis, data):
    redis_cache.set_agg_weather_data(data, "10001", "us")

    assert 0 < fake_redis.ttl(f"{KEY}_10001_us") <= 3600


def test_unit_group_is_part_of_the_key(fake_redis, data):
    redis_cache.set_agg_weather_data(data, "10001", "us")

    assert redis_cache.get_agg_weather_data("10001", "metric") is None


def test_zipcodes_do_not_collide(fake_redis, data):
    redis_cache.set_agg_weather_data(data, "10001", "us")

    assert redis_cache.get_agg_weather_data("10002", "us") is None


def test_clear_removes_only_that_entry(fake_redis, data):
    redis_cache.set_agg_weather_data(data, "10001", "us")
    redis_cache.set_agg_weather_data(data, "10001", "metric")

    redis_cache.clear_agg_weather_data("10001", "us")

    assert redis_cache.get_agg_weather_data("10001", "us") is None
    assert redis_cache.get_agg_weather_data("10001", "metric") is not None


@pytest.mark.parametrize("call", [
    lambda: redis_cache.get_agg_weather_data(None, "us"),
    lambda: redis_cache.clear_agg_weather_data(None, "us"),
    lambda: redis_cache.set_agg_weather_data(None, None, "us"),
])
def test_none_zipcode_is_rejected(fake_redis, call):
    with pytest.raises(ValueError):
        call()
