import requests
import json

from app import app
from public_settings import WEATHER_API_KEY
from .base import Sensor


class WeatherSensor(Sensor):
    LOOP_DELAY = 2  # TODO replace by 600

    def __init__(self, city_id=2654675):
        super(WeatherSensor, self).__init__()
        self.city_id = city_id

    def _iteration(self):
        response = requests.get(
            'http://api.openweathermap.org/data/2.5/weather',
            params={
                'id': self.city_id,
                'appid': WEATHER_API_KEY,
            },
        )

        data = response.json()

        self.set_value('humidity', data['main']['humidity'])
        self.set_value('temperature', data['main']['temp'])
        self.set_value('pressure', data['main']['pressure'])


weather = WeatherSensor()
weather.start()


@app.route('/sensors/weather/current/read')
def read_values():
    return json.dumps({
        'status': 'ok',
        'data': {
            'humidity': weather.get_value('humidity'),
            'temperature': weather.get_value('temperature'),
            'pressure': weather.get_value('pressure'),
        },
    })