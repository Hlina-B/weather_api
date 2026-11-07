from wapp.controller.weather_controller import app
from wapp.config.config_loader import get_config

config = get_config()

if __name__ == '__main__':
    app.run(debug=config.flask_debug, port=config.app_port)
