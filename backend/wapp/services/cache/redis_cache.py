from wapp.services.third_party_apis.api_strategy import ThirdPartyWeatherAPIStrategy
from wapp.models.weather_models import AggWeatherData
from wapp.config.config_loader import get_config

import redis
import logging

logger = logging.getLogger(__name__)
config = get_config()

# Redis key for AggWeatherData value
KEY = config.cache_key_prefix

# Look for redis config from env variable. If not found default to the default values
REDIS_HOST = config.redis_host
REDIS_PORT = int(config.redis_port)

logger.info(f"Redis_host: {REDIS_HOST}, Redis_port: {REDIS_PORT}")

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

def get_agg_weather_data(zp, unit_group) -> AggWeatherData:
    if zp is None:
        logger.error("Zipcode cannot be None")
        raise ValueError("Zipcode cannot be None")

    key = f"{KEY}_{zp}_{unit_group}"
    raw_json_data = r.get(key)
    agg_weather_data = AggWeatherData.model_validate_json(raw_json_data) if raw_json_data is not None else None
    return agg_weather_data

def clear_agg_weather_data(zipcode, unit_group):
    if zipcode is None:
        logger.error("Zipcode cannot be None")
        raise ValueError("Zipcode cannot be None")

    key = f"{KEY}_{zipcode}_{unit_group}"
    r.delete(key)

def set_agg_weather_data(data: AggWeatherData, zipcode, unit_group):
    if zipcode is None:
        logger.error("Zipcode cannot be None")
        raise ValueError("Zipcode cannot be None")
    
    key = f"{KEY}_{zipcode}_{unit_group}"
    r.set(key, data.model_dump_json(), ex=config.cache_ttl_seconds)

