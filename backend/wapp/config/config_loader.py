from wapp.services.third_party_apis.api_strategy import ThirdPartyWeatherAPIStrategy
from wapp.services.third_party_apis.visual_crossing import VisualCrossing

import os
from pathlib import Path
from functools import lru_cache
from dotenv import load_dotenv
from wapp.config.config_models import (
    AppConfig, 
    VisualCrossingConfig, 
    WeatherApiSource
)

root_dir = Path(__file__).parent.parent.parent #   change the root_dir of your .env file if applicable

def _load_weather_strategy(active_provider: str, timeout: int) -> ThirdPartyWeatherAPIStrategy:
    provider = WeatherApiSource(active_provider)
    if provider.value == WeatherApiSource.VISUALCROSSING.value:
        include=[inc.strip() for inc in os.getenv("VISUAL_CROSSING_INCLUDE", "hours,events,alerts").split(",") if inc]
        visual_cross_config = VisualCrossingConfig(
            api_key=os.environ["VISUAL_CROSSING_API_KEY"],
            domain=os.getenv("VISUAL_CROSSING_DOMAIN", "https://weather.visualcrossing.com"),
            path=os.getenv("VISUAL_CROSSING_PATH", "/VisualCrossingWebServices/rest/services/timeline/"),
            unit_group=os.getenv("VISUAL_CROSSING_UNIT_GROUP", "us"),
            include=include,
            content_type=os.getenv("VISUAL_CROSSING_CONTENT_TYPE", "json")
        )
        return VisualCrossing(visual_cross_config, timeout)
    # add your provider check here
    else:
        raise ValueError(f"Unsupported weather provider: '{provider}'")

def load_config() -> AppConfig:
    env_file = root_dir / f".env.{os.getenv('APP_ENV', 'dev')}"

    if not env_file.exists():
        raise FileNotFoundError(f"File not found in the given path: {env_file}")
    else:
        load_dotenv(dotenv_path=env_file, override=False)

    try:
        active_provider = os.getenv("WEATHER_PROVIDER")
        if active_provider is None or len(active_provider) == 0:
            active_provider = os.getenv("DEFAULT_WEATHER_API_SOURCE", "visualcrossing")
        timeout = int(os.getenv("HTTP_TIMEOUT_SECONDS", 10))

        return AppConfig(
            app_env=os.getenv("APP_ENV", "dev"),
            flask_debug=os.getenv("FLASK_DEBUG", "false") in ("true", "1", "yes"),
            app_host=os.environ["APP_HOST"],
            app_port=int(os.getenv("APP_PORT", 8080)),
            log_level=os.getenv("LOG_LEVEL", "DEBUG"),
            redis_host=os.environ["REDIS_HOST"],
            redis_port=int(os.getenv("REDIS_PORT", 6379)),
            redis_db=int(os.getenv("REDIS_DB", 0)),
            redis_password=os.getenv("REDIS_PASSWORD", ""),
            cache_ttl_seconds=int(os.getenv("CACHE_TTL_SECONDS", 3600)),
            cache_key_prefix=os.environ["CACHE_KEY_PREFIX"],
            http_timeout_seconds=timeout,
            rate_limit_default=os.getenv("RATE_LIMIT_DEFAULT", "60 per minute"),
            rate_limit_storage_uri=os.environ["RATE_LIMIT_STORAGE_URI"],
            cache_clear_token=os.getenv("CACHE_CLEAR_TOKEN", "dev-only-token"),
            weather_api_source=active_provider,
            strategy=_load_weather_strategy(active_provider, timeout)
        )
    except KeyError as missing_key:
        raise RuntimeError(f"Missing required environment variable: {missing_key}") from None
    except ValueError as parse_err:
        raise RuntimeError(f"Configuration validation failed: {parse_err}") from None
    

@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """Reads once at startup and memoizes the result.""" 
    return load_config()
