# Weather API

A small weather service for US ZIP codes. It fetches forecasts from a third-party weather API, caches them in Redis, rate-limits clients, and serves a simple web UI.

Visual Crossing is the default weather provider. The provider sits behind an interface, so you can add a different one without changing the rest of the app (see [Adding a weather provider](#adding-a-weather-provider)).

This is a practice project based on the [roadmap.sh Weather API project](https://roadmap.sh/projects/weather-api-wrapper-service).

## Features

- Current conditions, a 24-hour outlook and a 15-day forecast for any 5-digit US ZIP code
- US, metric, UK and base (Kelvin) units
- Redis cache with a configurable expiry, keyed by ZIP code and units
- Per-client rate limiting with counters stored in Redis
- Times shown in the location's own time zone, including on daylight-saving days
- Separate dev and prod configuration through `.env` files
- A plain HTML/CSS/JS front end with light and dark mode
- A test suite that needs no Redis server or API key

## How it works

```
Browser ──► Flask controller ──► Weather service ──► Redis cache
                                        │                (hit: return cached forecast)
                                        ▼
                                Weather provider ──► Visual Crossing API
                                (strategy interface)     (miss: fetch, map, cache)
```

1. The **controller** (`weather_controller.py`) validates the ZIP code and units, applies rate limits, and turns errors into HTTP status codes.
2. The **service** (`weather_service.py`) checks the cache. On a miss it asks the configured provider and caches the result. It then picks the current hour's conditions using the location's time zone. The current conditions are worked out on every request and never cached, so they stay current while the forecast is cached.
3. The **provider** (`visual_crossing.py`) calls the third-party API and maps its response to the app's own models (`weather_models.py`), using one field map per model. A check at startup fails if a map and its model drift apart.
4. The **cache** (`redis_cache.py`) stores forecasts as JSON under `{CACHE_KEY_PREFIX}_{zipcode}_{unit_group}` and lets them expire after `CACHE_TTL_SECONDS`.

## Project structure

```
backend/
├── app.py                          # Starts the Flask server
├── .env.example                    # Template for the env files (committed)
├── .env.dev / .env.prod            # Your real settings (not committed)
├── pytest.ini
├── requirements.txt
├── pyproject.toml
├── frontend/                       # Web UI
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── wapp/
│   ├── config/
│   │   ├── config_loader.py        # Reads .env.<APP_ENV> and builds AppConfig
│   │   └── config_models.py        # AppConfig, provider configs, provider enum
│   ├── controller/
│   │   └── weather_controller.py   # Routes, validation, rate limiting
│   ├── models/
│   │   └── weather_models.py       # Pydantic models for the API response
│   └── services/
│       ├── weather_service.py      # Cache-or-fetch logic, current conditions
│       ├── cache/redis_cache.py
│       ├── helper/
│       │   ├── http_request_helper.py
│       │   └── time_handler.py
│       └── third_party_apis/
│           ├── api_strategy.py     # Interface every provider implements
│           └── visual_crossing.py  # Visual Crossing provider
└── tests/
```

## Getting started

### Requirements

- Python 3.10 or newer (developed on 3.13)
- Redis, running locally or reachable over the network
- A free [Visual Crossing API key](https://www.visualcrossing.com/weather-api)

The quickest way to run Redis is Docker:

```bash
docker run -d --name weather-redis -p 6379:6379 redis:7
```

On Windows without Docker, use WSL or Memurai.

### Install

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate | .\.venv\Scripts\Activate.ps1    #powershell
pip install flask flask-limiter redis requests pydantic python-dotenv tzdata | pip install -r requirements.txt
```

`tzdata` is required on Windows, which doesn't ship the time-zone database Python's `zoneinfo` reads. It is harmless elsewhere.

### Configure

Copy the template and fill in your API key:

```bash
cp .env.example .env.dev
```

The app loads `.env.<APP_ENV>` from the `backend/` folder. `APP_ENV` defaults to `dev`. Real environment variables take priority over values in the file.

| Variable | Required | Default | What it does |
| --- | --- | --- | --- |
| `APP_ENV` | No | `dev` | Which env file to load: `.env.dev` or `.env.prod` |
| `FLASK_DEBUG` | No | `false` | Flask debug mode. Never turn it on in production |
| `APP_HOST` | Yes | | Host address the app is configured for |
| `APP_PORT` | No | `8080` | Port the server listens on |
| `LOG_LEVEL` | No | `DEBUG` | Logging level |
| `WEATHER_PROVIDER` | No | | Active weather provider. Overrides `DEFAULT_WEATHER_API_SOURCE` |
| `DEFAULT_WEATHER_API_SOURCE` | No | `visualcrossing` | Provider used when `WEATHER_PROVIDER` isn't set |
| `HTTP_TIMEOUT_SECONDS` | No | `10` | How long to wait for the weather provider |
| `VISUAL_CROSSING_API_KEY` | Yes | | Your Visual Crossing key. Keep it secret |
| `VISUAL_CROSSING_DOMAIN` | No | `https://weather.visualcrossing.com` | API host |
| `VISUAL_CROSSING_PATH` | No | `/VisualCrossingWebServices/rest/services/timeline/` | API path |
| `VISUAL_CROSSING_UNIT_GROUP` | No | `us` | Default units when a request doesn't set them |
| `VISUAL_CROSSING_INCLUDE` | No | `hours,events,alerts` | Comma-separated sections to request |
| `VISUAL_CROSSING_CONTENT_TYPE` | No | `json` | Response format |
| `REDIS_HOST` | Yes | | Redis host |
| `REDIS_PORT` | No | `6379` | Redis port |
| `REDIS_DB` | No | `0` | Redis database for the cache |
| `REDIS_PASSWORD` | No | | Redis password |
| `CACHE_TTL_SECONDS` | No | `3600` | How long a cached forecast lives |
| `CACHE_KEY_PREFIX` | Yes | | Prefix for cache keys. Use different prefixes for dev and prod |
| `RATE_LIMIT_DEFAULT` | No | `60 per minute` | Request limit per client IP |
| `RATE_LIMIT_STORAGE_URI` | Yes | | Where rate-limit counters live, e.g. `redis://localhost:6379/1` |
| `CACHE_CLEAR_TOKEN` | No | `dev-only-token` | Enables the cache-clear endpoint when set to `dev-only-token` |

The rate limiter uses Redis database 1 and the cache uses database 0, so clearing the cache never resets anyone's rate limits.

### Run

```bash
python app.py
```

To use the prod settings, set `APP_ENV` first:

```bash
APP_ENV=prod python app.py         # Windows PowerShell: $env:APP_ENV="prod"; python app.py
```

Then open `http://127.0.0.1:8080/` for the web UI, or call the API directly.

The app runs on Flask's built-in development server, which is fine for this project. For anything public, run it behind a production WSGI server such as gunicorn.

## API

### Get the forecast

```
GET /weather?zipcode=10001&unit_group=us
```

| Parameter | Required | Values |
| --- | --- | --- |
| `zipcode` | Yes | A 5-digit US ZIP code. Leading zeros are kept, e.g. `02134` |
| `unit_group` | Yes | `us` (°F, mph, in), `metric` (°C, km/h, mm), `uk` (°C, mph, mm), `base` (K, m/s, mm) |

A successful response (`200`) looks like this, shortened:

```json
{
  "current_snapshot": {
    "date_time": { "date_time": "14:00:00", "date_time_epoch": 1793905200 },
    "temperature": { "temp": 54.0, "feels_like": 51.0, "dew_point": 30.0 },
    "conditions": { "weather_icon": "partly-cloudy-day", "condits": "Partially cloudy" },
    "wind_and_pressure": { "wind_speed": 5.0, "wind_gust": 12.0, "wind_direction": 180.0, "sea_level_pressure": 1015.0 }
  },
  "hourly_forecast": { "2026-11-05": { "1793905200": { "...": "one WeatherData per hour" } } },
  "daily_forecast":  { "2026-11-05": { "...": "one WeatherData per day" } },
  "location_info": {
    "zip_code": "10001",
    "resolved_address": "New York, NY 10001, United States",
    "latitude": 40.75,
    "longitude": -73.99,
    "time_zone": "America/New_York",
    "tzoffset": -5
  },
  "info": { "stations_map": {}, "alerts": [] }
}
```

- `daily_forecast` is keyed by local date (`YYYY-MM-DD`).
- `hourly_forecast` is keyed by local date, then by the hour's Unix epoch as a string. Epoch keys stay unique on daylight-saving days, when a local hour is skipped or repeated.

| Status | When |
| --- | --- |
| `200` | Forecast returned |
| `400` | Missing or invalid `zipcode` or `unit_group`, or no data for the current hour |
| `429` | Rate limit reached |
| `500` | The weather provider failed, timed out, or returned data that couldn't be mapped |

Errors return JSON: `{"error": "A 5 digits zipcode is required"}`.

### Clear cached data (development only)

```
DELETE /weather/clear?zipcode=10001&unit_group=us
```

Removes one cached forecast so the next request fetches fresh data. It only works when `CACHE_CLEAR_TOKEN` is `dev-only-token`, and otherwise returns `401`. It is limited to 60 calls per hour. This is a development switch, not authentication: the request itself is never checked.

## Web UI

The `frontend/` folder is a static page that calls the API. The easiest way to use it is to let Flask serve it, so the page and the API share an origin and no CORS setup is needed:

```python
app = Flask(__name__, static_folder="../../frontend", static_url_path="")

@app.route("/")
def index():
    return app.send_static_file("index.html")
```

The page shows:

- the current conditions on a panel colored like the sky at that location right now
- a 24-hour temperature curve with the chance of rain
- the 15-day forecast; select a day to see its hours on the curve
- any weather alerts

It remembers your last search. If you open `index.html` directly from disk instead, it calls `http://127.0.0.1:8080`, and Flask then needs CORS enabled, for example with `flask-cors`.

## Tests

```bash
pip install -r requirements.txt
pytest
```

The tests don't need Redis, an API key or a network connection:

- `fakeredis` stands in for Redis.
- A fake HTTP function returns realistic Visual Crossing responses.
- `conftest.py` loads a test config before the app modules import.

| File | What it checks |
| --- | --- |
| `test_visual_crossing.py` | Every field is mapped to the right place; the URL and query; epoch keys, including a 25-hour daylight-saving day; error handling; the startup map check |
| `test_weather_service.py` | Cache hit vs. miss; units passed to the provider; the current hour in the location's time zone; the snapshot is never cached |
| `test_redis_cache.py` | Cache hits return full models; expiry; keys separate by ZIP code and units; clearing |
| `test_weather_controller.py` | Input validation; status codes for each error type; the dev-only clear endpoint; rate limiting |
| `test_config_loader.py` | Type conversion; building the provider; env vars override the file; clear errors for missing or bad values |
| `test_helpers.py` | Rounding to the current hour; HTTP timeout and error handling |

## Adding a weather provider

The service only talks to the `ThirdPartyWeatherAPIStrategy` interface, so a new provider doesn't touch the controller, service or cache.

1. **Add the provider name** to `WeatherApiSource` in `config_models.py`.
2. **Add a config class** for its settings in `config_models.py`, subclassing `WeatherProviderConfig`.
3. **Implement the strategy** in `services/third_party_apis/`. Subclass `ThirdPartyWeatherAPIStrategy` and implement `fetch_map_data(zipcode, unit_group=None)`, returning an `AggWeatherData` that follows these rules:
   - `daily_forecast` keyed by local date (`YYYY-MM-DD`)
   - `hourly_forecast` keyed by local date, then by the hour's epoch as a string
   - `location_info.time_zone` set to an IANA name such as `America/New_York`
   - `current_snapshot` left as `None`, since the service fills it in
4. **Build it from config** with a new branch in `_load_weather_strategy` in `config_loader.py`, reading the provider's env vars.
5. **Add its env vars** to `.env.example` and your env files, and set `WEATHER_PROVIDER` to the new name.
6. **Add tests** with a saved response from the new API, following `test_visual_crossing.py`.

## Known limitations

- Only 5-digit US ZIP codes are accepted.
- Finding the current hour assumes the location's UTC offset is a whole number of hours. That holds for every US time zone, but not, for example, for India (+5:30).
- The cache-clear endpoint is a development switch, not authentication.
- Error messages from internal failures are returned to the client as-is, which is fine for a this purpose but would leak details in production.