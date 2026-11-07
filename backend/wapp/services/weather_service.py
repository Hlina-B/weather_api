from zoneinfo import ZoneInfo

from wapp.services.cache import redis_cache as rds
from wapp.services.helper import time_handler as th
from wapp.models.weather_models import AggWeatherData
from wapp.config.config_loader import get_config

from datetime import datetime
import copy
import logging 

logger = logging.getLogger(__name__)
config = get_config()


def get_weather_data(zp: str, unit_group: str) -> AggWeatherData:
    print(f"Zipcode: {type(zp)}")
    agg_weather_data = rds.get_agg_weather_data(zp, unit_group)

    if agg_weather_data is None:
        agg_weather_data: AggWeatherData = config.strategy.fetch_map_data(zipcode=zp, unit_group=unit_group)
        rds.set_agg_weather_data(agg_weather_data, zp, unit_group)


    if agg_weather_data.current_snapshot is None:
        time_str = th.current_hour_start_epoch()
        
        tz = ZoneInfo(agg_weather_data.location_info.time_zone)
        date_str = datetime.fromtimestamp(int(time_str), tz).strftime("%Y-%m-%d")
        today_weather_data = agg_weather_data.hourly_forecast.get(date_str)
        if today_weather_data is None:
            logger.error("No weather data found for the current date")
            raise ValueError(f"No weather data found for the current date: {date_str}")

        current = copy.deepcopy(today_weather_data.get(time_str))
        if current is None:
            logger.error("No weather data found for the current time")
            raise ValueError(f"No weather data found for the current time: {time_str}")
        agg_weather_data.current_snapshot = current

    return agg_weather_data

def clear_weather_data(zipcode: str, unit_group: str):
    rds.clear_agg_weather_data(zipcode, unit_group)
