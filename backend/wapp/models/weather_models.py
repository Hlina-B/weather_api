from pydantic import BaseModel
from typing import Optional


class WeatherDateAndTime(BaseModel):
    date_time: str 
    date_time_epoch: int

class Temperature(BaseModel):
    temp: float
    max_temp: Optional[float] = None
    min_temp: Optional[float] = None
    avg_temp: Optional[float] = None
    source: str
    max_feels_like: Optional[float] = None
    min_feels_like: Optional[float] = None
    feels_like: Optional[float] = None
    dew_point: Optional[float] = None
    stations: Optional[list[str]] = None

class HumidityAndClouds(BaseModel):
    relative_humidity: float
    cloud_cover: float
    visibility: float

class Precipitation(BaseModel):
    precip: float
    snowfall: float
    snow_depth: float
    precip_chance: Optional[int] = None
    precip_cover: Optional[float] = None
    precip_type: Optional[list[str]] = None

class WindAndPressure(BaseModel):
    wind_speed: float
    wind_gust: float
    wind_direction: float
    sea_level_pressure: float

class Solar(BaseModel):
    solar_radiation: float
    solar_energy: Optional[float] = None
    uv_index: Optional[float] = None

class Astronomy(BaseModel):
    sunrise: Optional[str]
    sunrise_epoch: Optional[int]
    sunset: Optional[str]
    sunset_epoch: Optional[int]
    moon_phase: Optional[float]

class Conditions(BaseModel):
    weather_icon: str
    description: Optional[str]
    condits: Optional[str]

class SevereWeather(BaseModel):
    severe_risk: Optional[int]

class LocationInfo(BaseModel):
    zip_code: str
    resolved_address: str
    latitude: float
    longitude: float
    time_zone: str
    tzoffset: int

class Info(BaseModel):
    stations_map: dict[str, dict]
    alerts: Optional[list]

class WeatherData(BaseModel):
    date_time: WeatherDateAndTime
    temperature: Temperature 
    humidity_and_clouds: HumidityAndClouds 
    precipitation: Precipitation 
    wind_and_pressure: WindAndPressure
    solar: Solar
    astronomy: Astronomy
    conditions: Conditions
    severe_weather: SevereWeather
    source: str
    

class AggWeatherData(BaseModel):
    current_snapshot: Optional[WeatherData] 
    hourly_forecast: dict[str, dict[str, WeatherData]]
    daily_forecast: dict[str, WeatherData]
    location_info: LocationInfo
    info: Info