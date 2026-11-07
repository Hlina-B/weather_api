"""Test setup.

Several app modules call get_config() at import time (redis_cache, weather_service,
weather_controller). To keep tests independent of your .env files and a running
Redis, get_config is pointed at a test config *before* those modules are imported.
"""
from dataclasses import replace

import fakeredis
import pytest

import wapp.config.config_loader as config_loader
from wapp.config.config_models import AppConfig, VisualCrossingConfig

VC_CONFIG = VisualCrossingConfig(
    api_key="test-key",
    domain="https://weather.example.com",
    path="/timeline/",
    unit_group="us",
    include=["hours", "events", "alerts"],
    content_type="json",
)

TEST_CONFIG = AppConfig(
    app_env="test",
    flask_debug=False,
    app_host="127.0.0.1",
    app_port=8080,
    log_level="DEBUG",
    redis_host="localhost",
    redis_port=6379,
    redis_db=0,
    redis_password="",
    cache_ttl_seconds=3600,
    cache_key_prefix="test_agg_weather_data",
    http_timeout_seconds=5,
    rate_limit_default="1000 per minute",
    rate_limit_storage_uri="memory://",  # no Redis needed for the limiter in tests
    cache_clear_token="dev-only-token",
    weather_api_source="visualcrossing",
    strategy=None,  # each test that needs one injects a FakeStrategy
)

config_loader.get_config = lambda: TEST_CONFIG


@pytest.fixture
def fake_redis(monkeypatch):
    """Replace the module-level Redis client with an in-memory one."""
    from wapp.services.cache import redis_cache

    client = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_cache, "r", client)
    return client


@pytest.fixture
def use_strategy(monkeypatch):
    """Install a strategy into the service's config: use_strategy(FakeStrategy(...))."""
    from wapp.services import weather_service

    def _install(strategy):
        monkeypatch.setattr(weather_service, "config", replace(weather_service.config, strategy=strategy))
        return strategy

    return _install


@pytest.fixture
def now_is(monkeypatch):
    """Freeze "current hour": now_is("1762369200")."""
    from wapp.services.helper import time_handler

    def _set(epoch: str):
        monkeypatch.setattr(time_handler, "current_hour_start_epoch", lambda: epoch)

    return _set
