from wapp.services.third_party_apis.api_strategy import ThirdPartyWeatherAPIStrategy

from dataclasses import dataclass
from enum import Enum
from abc import ABC

class WeatherApiSource(Enum):
    VISUALCROSSING = "visualcrossing"

class WeatherProviderConfig(ABC):
    """Base marker class for any weather provider settings."""


@dataclass(frozen=True)
class VisualCrossingConfig(WeatherProviderConfig):
    api_key: str
    domain: str
    path: str
    unit_group: str
    include: list
    content_type: str

@dataclass(frozen=True)
class AppConfig:
    app_env: str
    flask_debug: bool
    app_host: str
    app_port: int
    log_level: str
    redis_host: str
    redis_port: int
    redis_db: int
    redis_password: str
    cache_ttl_seconds: int
    cache_key_prefix: str
    http_timeout_seconds: int
    rate_limit_default: str
    rate_limit_storage_uri: str
    cache_clear_token: str 
    weather_api_source: str
    strategy: ThirdPartyWeatherAPIStrategy
