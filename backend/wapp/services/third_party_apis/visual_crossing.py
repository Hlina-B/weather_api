import logging
from typing import Any, Callable, Mapping, Optional
from urllib.parse import quote, urlencode
from requests.exceptions import ConnectionError, HTTPError, RequestException, Timeout

from pydantic import BaseModel

from wapp.config.config_models import VisualCrossingConfig
from wapp.models.weather_models import (
    AggWeatherData,
    Astronomy,
    Conditions,
    HumidityAndClouds,
    Info,
    LocationInfo,
    Precipitation,
    SevereWeather,
    Solar,
    Temperature,
    WeatherData,
    WeatherDateAndTime,
    WindAndPressure,
)
from wapp.services.helper.http_request_helper import http_request
from wapp.services.third_party_apis.api_strategy import ThirdPartyWeatherAPIStrategy

logger = logging.getLogger(__name__)

RawRecord = Mapping[str, Any]


# -----------------------------------------------------------------------------
# Field maps: our model field name -> Visual Crossing JSON key.
# Adding or renaming a field is a one-line change here; no method to touch.
# -----------------------------------------------------------------------------
_DATE_TIME_MAP = {
    "date_time": "datetime",
    "date_time_epoch": "datetimeEpoch",
}

_TEMPERATURE_MAP = {
    "max_temp": "tempmax",
    "min_temp": "tempmin",
    "temp": "temp",
    "max_feels_like": "feelslikemax",
    "min_feels_like": "feelslikemin",
    "feels_like": "feelslike",
    "dew_point": "dew",
    "stations": "stations",
    "source": "source",
}

_HUMIDITY_AND_CLOUDS_MAP = {
    "relative_humidity": "humidity",
    "cloud_cover": "cloudcover",
    "visibility": "visibility",
}

_PRECIPITATION_MAP = {
    "precip": "precip",
    "snowfall": "snow",
    "snow_depth": "snowdepth",
    "precip_chance": "precipprob",
    "precip_cover": "precipcover",
    "precip_type": "preciptype",
}

_WIND_AND_PRESSURE_MAP = {
    "wind_speed": "windspeed",
    "wind_gust": "windgust",
    "wind_direction": "winddir",
    "sea_level_pressure": "pressure",
}

_SOLAR_MAP = {
    "solar_radiation": "solarradiation",
    "solar_energy": "solarenergy",
    "uv_index": "uvindex",
}

_ASTRONOMY_MAP = {
    "sunrise": "sunrise",
    "sunrise_epoch": "sunriseEpoch",
    "sunset": "sunset",
    "sunset_epoch": "sunsetEpoch",
    "moon_phase": "moonphase",
}

_CONDITIONS_MAP = {
    "weather_icon": "icon",
    "description": "description",
    "condits": "conditions",
}

_SEVERE_WEATHER_MAP = {
    "severe_risk": "severerisk",
}

_LOCATION_MAP = {
    "zip_code": "address",
    "resolved_address": "resolvedAddress",
    "latitude": "latitude",
    "longitude": "longitude",
    "time_zone": "timezone",
    "tzoffset": "tzoffset",
}

_INFO_MAP = {
    "stations_map": "stations",
    "alerts": "alerts",
}


class VisualCrossingResponseError(RuntimeError):
    """Visual Crossing returned a response that cannot be mapped.

    Move this into a shared exceptions module when you work on error handling,
    so the controller can turn it into the right HTTP status.
    """
class WeatherAppError(RuntimeError):
    """Internal Exceptions (500)"""


def _build(model: type[BaseModel], raw: RawRecord, field_map: Mapping[str, str], **computed: Any):
    """Create `model` from `raw` using `field_map`, plus any computed fields."""
    values = {field: raw.get(key) for field, key in field_map.items()}
    values.update(computed)
    return model(**values)


def _check_map(model: type[BaseModel], field_map: Mapping[str, str], computed: frozenset = frozenset()) -> None:
    """Fail at import time, not on a user's request, if a map and its model drift apart."""
    model_fields = model.model_fields
    unknown = set(field_map) - set(model_fields)
    required = {name for name, info in model_fields.items() if info.is_required()}
    missing = required - set(field_map) - computed
    if unknown or missing:
        raise TypeError(
            f"{model.__name__} field map is out of sync. "
            f"Unknown fields: {sorted(unknown)}. Missing required fields: {sorted(missing)}."
        )


_check_map(WeatherDateAndTime, _DATE_TIME_MAP)
_check_map(Temperature, _TEMPERATURE_MAP, frozenset({"avg_temp"}))
_check_map(HumidityAndClouds, _HUMIDITY_AND_CLOUDS_MAP)
_check_map(Precipitation, _PRECIPITATION_MAP)
_check_map(WindAndPressure, _WIND_AND_PRESSURE_MAP)
_check_map(Solar, _SOLAR_MAP)
_check_map(Astronomy, _ASTRONOMY_MAP)
_check_map(Conditions, _CONDITIONS_MAP)
_check_map(SevereWeather, _SEVERE_WEATHER_MAP)
_check_map(LocationInfo, _LOCATION_MAP)
_check_map(Info, _INFO_MAP)


class VisualCrossing(ThirdPartyWeatherAPIStrategy):
    """Fetches forecasts from Visual Crossing and maps them to the app's models."""
    
    def __init__(
        self,
        config: VisualCrossingConfig,
        timeout: int = 10,
        fetch_json: Callable[[str], Optional[dict]] = http_request,
    ) -> None:
        if not config.api_key:
            raise ValueError("Visual Crossing API key is missing. Set it in your .env file.")
        self._config = config
        self.timeout = timeout
        # Injectable so tests can pass a fake that returns a saved JSON fixture.
        self._fetch_json = fetch_json

    @property
    def config(self) -> VisualCrossingConfig:
        return self._config

    def fetch_map_data(self, zipcode: str,unit_group: Optional[str] = None) -> AggWeatherData:
        if not zipcode:
            raise ValueError("zipcode is required.")
        try:
            raw = self._fetch_json(self._build_url(zipcode, unit_group), self.timeout)
            if not raw:
                raise VisualCrossingResponseError("Empty response from Visual Crossing.")
            
        except HTTPError as http_err:
            logger.error(f"Visual Crossing HTTP Error {http_err.response.status_code}: {http_err.response.text}")
            raise VisualCrossingResponseError("Visual Crossing HTTP Error")

        except Timeout as tout:
            logger.error(f"Visual Crossing Request Timed Out: {tout}")
            raise VisualCrossingResponseError(f"The request timed out")

        except ConnectionError as ce:
            logger.error(f"Visual Crossing Failed to establish a network connection: {ce}")
            raise VisualCrossingResponseError(f"Failed to establish a network connection.")

        except RequestException as re:
            logger.error(f"Visual Crossing an unexpected requests error occurred:  {re}")
            raise VisualCrossingResponseError(f"An unexpected requests error occurred")
        
        except RuntimeError as rte:
            logger.error(f"Visual Crossing Runtime Error: {rte}")
            raise VisualCrossingResponseError(rte)
        
        except Exception as e:
            logger.error(f"Visual Crossing An unexpected error occurred: {e}")
            raise VisualCrossingResponseError(f"An unexpected error occurred")

        return self._map_response(raw)

    # -------------------------------------------------------------------------
    # Request
    # -------------------------------------------------------------------------
    def _build_url(self, zipcode: str, unit_group: Optional[str]) -> str:
        # urlencode handles escaping (e.g. the commas in include).
        # The URL contains the API key: never log it.
        query = urlencode({
            "unitGroup": unit_group or self._config.unit_group,
            "include": ",".join(self._config.include),
            "contentType": self._config.content_type,
            "key": self._config.api_key,
        })
        location = quote(zipcode, safe="")
        return f"{self._config.domain}{self._config.path}{location}?{query}"

    # -------------------------------------------------------------------------
    # Mapping
    # -------------------------------------------------------------------------
    def _map_response(self, raw: RawRecord) -> AggWeatherData:
        try:
            days = raw.get("days")
            if not isinstance(days, list) or not days:
                raise VisualCrossingResponseError("Response contains no daily forecast.")

            daily_forecast: dict[str, WeatherData] = {}
            hourly_forecast: dict[str, dict[str, WeatherData]] = {}

            for day in days:
                day_data = self._map_weather(day)
                date_key = day_data.date_time.date_time

                hours = day.get("hours")
                if not hours:
                    raise VisualCrossingResponseError(f"No hourly data for {date_key}.")

                daily_forecast[date_key] = day_data
                hourly_forecast[date_key] = self._map_hours(hours)

            return AggWeatherData(
                current_snapshot=None,
                hourly_forecast=hourly_forecast,
                daily_forecast=daily_forecast,
                location_info=_build(LocationInfo, raw, _LOCATION_MAP),
                info=_build(Info, raw, _INFO_MAP),
            )
        except Exception as ex:
            raise WeatherAppError(ex)

    def _map_hours(self, hours: list[RawRecord]) -> dict[str, WeatherData]:
        # Keyed by epoch, so DST days (a repeated or missing hour) stay unambiguous.
        mapped: dict[str, WeatherData] = {}
        for hour in hours:
            hour_data = self._map_weather(hour)
            mapped[str(hour_data.date_time.date_time_epoch)] = hour_data
        return mapped

    @staticmethod
    def _map_weather(raw: RawRecord) -> WeatherData:
        return WeatherData(
            date_time=_build(WeatherDateAndTime, raw, _DATE_TIME_MAP),
            temperature=_build(
                Temperature, raw, _TEMPERATURE_MAP,
                avg_temp=VisualCrossing._average(raw.get("tempmax"), raw.get("tempmin")),
            ),
            humidity_and_clouds=_build(HumidityAndClouds, raw, _HUMIDITY_AND_CLOUDS_MAP),
            precipitation=_build(Precipitation, raw, _PRECIPITATION_MAP),
            wind_and_pressure=_build(WindAndPressure, raw, _WIND_AND_PRESSURE_MAP),
            solar=_build(Solar, raw, _SOLAR_MAP),
            astronomy=_build(Astronomy, raw, _ASTRONOMY_MAP),
            conditions=_build(Conditions, raw, _CONDITIONS_MAP),
            severe_weather=_build(SevereWeather, raw, _SEVERE_WEATHER_MAP),
            source=raw.get("source"),
        )

    @staticmethod
    def _average(high: Optional[float], low: Optional[float]) -> Optional[float]:
        if high is None or low is None:
            return None
        return (high + low) / 2