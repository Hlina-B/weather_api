from abc import ABC, abstractmethod
from typing import Optional

from wapp.models.weather_models import AggWeatherData

class ThirdPartyWeatherAPIStrategy(ABC):
    @abstractmethod
    def fetch_map_data(self, zipcode: str, unit_group: Optional[str] = None) -> AggWeatherData:
         """Fetch the forecast for `zipcode` and map it to AggWeatherData. `unit_group` overrides the provider's configured default units when given."""

