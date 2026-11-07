"""The app can't start without valid config, so loading must work and fail clearly."""
import os

import pytest

from wapp.config import config_loader
from wapp.services.third_party_apis.visual_crossing import VisualCrossing

VALID_ENV = """\
APP_ENV=test
FLASK_DEBUG=true
APP_HOST=127.0.0.1
APP_PORT=8080
LOG_LEVEL=INFO
DEFAULT_WEATHER_API_SOURCE=visualcrossing
HTTP_TIMEOUT_SECONDS=7
VISUAL_CROSSING_API_KEY=file-key
VISUAL_CROSSING_UNIT_GROUP=metric
VISUAL_CROSSING_INCLUDE=hours, alerts
REDIS_HOST=localhost
REDIS_PORT=6380
REDIS_DB=2
CACHE_TTL_SECONDS=120
CACHE_KEY_PREFIX=test_prefix
RATE_LIMIT_DEFAULT=10 per minute
RATE_LIMIT_STORAGE_URI=redis://localhost:6379/1
CACHE_CLEAR_TOKEN=dev-only-token
"""


@pytest.fixture
def env_dir(tmp_path, monkeypatch):
    """Point the loader at a temp folder and give each test a clean environment.

    load_dotenv writes into os.environ, so the whole environment is snapshotted
    and restored, or values would leak into the next test.
    """
    saved = dict(os.environ)
    for key in list(os.environ):
        if key.startswith(("APP_", "FLASK_", "REDIS_", "CACHE_", "RATE_", "VISUAL_", "HTTP_", "WEATHER_", "DEFAULT_", "LOG_")):
            del os.environ[key]
    os.environ["APP_ENV"] = "test"
    monkeypatch.setattr(config_loader, "root_dir", tmp_path)
    yield tmp_path
    os.environ.clear()
    os.environ.update(saved)


def write_env(folder, text=VALID_ENV, name=".env.test"):
    (folder / name).write_text(text)


def test_loads_and_converts_values(env_dir):
    write_env(env_dir)
    config = config_loader.load_config()

    assert config.flask_debug is True
    assert config.redis_port == 6380
    assert config.redis_db == 2
    assert config.cache_ttl_seconds == 120
    assert config.http_timeout_seconds == 7
    assert config.cache_key_prefix == "test_prefix"


def test_builds_the_visual_crossing_strategy(env_dir):
    write_env(env_dir)
    strategy = config_loader.load_config().strategy

    assert isinstance(strategy, VisualCrossing)
    assert strategy.config.api_key == "file-key"
    assert strategy.config.unit_group == "metric"
    assert strategy.config.include == ["hours", "alerts"]  # split and stripped
    assert strategy.timeout == 7


def test_real_environment_variables_override_the_file(env_dir):
    write_env(env_dir)
    os.environ["APP_PORT"] = "9999"

    assert config_loader.load_config().app_port == 9999


def test_missing_env_file_names_the_path(env_dir):
    with pytest.raises(FileNotFoundError, match=r"\.env\.test"):
        config_loader.load_config()


@pytest.mark.parametrize("missing", ["VISUAL_CROSSING_API_KEY", "REDIS_HOST", "CACHE_KEY_PREFIX"])
def test_missing_required_variable_is_reported_by_name(env_dir, missing):
    write_env(env_dir, "\n".join(l for l in VALID_ENV.splitlines() if not l.startswith(missing + "=")))

    with pytest.raises(RuntimeError, match=missing):
        config_loader.load_config()


def test_unsupported_provider_is_rejected(env_dir):
    write_env(env_dir, VALID_ENV.replace("DEFAULT_WEATHER_API_SOURCE=visualcrossing", "DEFAULT_WEATHER_API_SOURCE=nope"))

    with pytest.raises(RuntimeError, match="nope"):
        config_loader.load_config()


def test_weather_provider_variable_takes_precedence(env_dir):
    write_env(env_dir, VALID_ENV.replace("DEFAULT_WEATHER_API_SOURCE=visualcrossing", "DEFAULT_WEATHER_API_SOURCE=nope"))
    os.environ["WEATHER_PROVIDER"] = "visualcrossing"

    assert isinstance(config_loader.load_config().strategy, VisualCrossing)


def test_non_numeric_port_is_reported(env_dir):
    write_env(env_dir, VALID_ENV.replace("APP_PORT=8080", "APP_PORT=eighty"))

    with pytest.raises(RuntimeError, match="validation failed"):
        config_loader.load_config()
