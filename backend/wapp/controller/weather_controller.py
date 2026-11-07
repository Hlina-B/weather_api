from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from wapp.services import weather_service as service
from wapp.config.config_models import WeatherApiSource
from wapp.config.config_loader import get_config

config = get_config()
app = Flask(__name__)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[config.rate_limit_default],
    storage_uri=config.rate_limit_storage_uri
)

@app.route('/weather', methods=['GET'])
def get_weather():
    zipcode: str = request.args.get('zipcode')
    unit_group = request.args.get('unit_group')

    if unit_group is None or len(unit_group.strip()) == 0 or not (unit_group.strip() in ["us", "metric", "uk", "base"]):
            return jsonify({"error": "please provide unit_group and the value has to be one of (us, metric, uk, base)"}), 400

    if not zipcode or not zipcode.isdigit() or len(zipcode) != 5:
        return jsonify({"error": "A 5 digits zipcode is required"}), 400
    
    try:
        weather_data = service.get_weather_data(zipcode, unit_group)
        return jsonify(weather_data.model_dump()), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

#--------------------------------------------------------------------------------------
# Dev convenience only: this endpoint is open in dev and disabled elsewhere.
# It is NOT authentication. The request is never checked.
#--------------------------------------------------------------------------------------
@app.route('/weather/clear', methods=['DELETE'])
@limiter.limit("60 per hour", methods=["DELETE"])
def clear_weather():
    if config.cache_clear_token != "dev-only-token":
        return jsonify({"error": "Unauthorzied"}), 401
    
    zipcode = request.args.get('zipcode')
    unit_group = request.args.get('unit_group')

    if not zipcode or not zipcode.isdigit() or len(zipcode) != 5:
        return jsonify({"error": "A 5 digits zipcode is required"}), 400

    try:
        service.clear_weather_data(zipcode, unit_group)
        return jsonify({"message": f"Weather data for zipcode {zipcode} cleared from cache"}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500