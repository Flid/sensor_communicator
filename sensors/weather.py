import requests
import json
import logging

from app import app
from prod_config import WEATHER_API_KEY
from .base import Sensor

log = logging.getLogger(__name__)

# There are lots of possible rain types, let's get value to each,
# assuming that 1 is a usual rain

WEATHER_CODE_RAIN_WEIGHTS = {
    200: 0.5,  # thunderstorm with light rain
    201: 1.0,  # thunderstorm with rain
    202: 1.5,  # thunderstorm with heavy rain
    210: 0.1,  # light thunderstorm
    211: 0.1,  # thunderstorm
    212: 0.1,  # heavy thunderstorm
    221: 0.1,  # ragged thunderstorm
    230: 0.3,  # thunderstorm with light drizzle
    231: 0.5,  # thunderstorm with drizzle
    232: 1.0,  # thunderstorm with heavy drizzle
    300: 0.1,  # light intensity drizzle
    301: 0.5,  # drizzle
    302: 1.0,  # heavy intensity drizzle
    310: 0.5,  # light intensity drizzle rain
    311: 1.0,  # drizzle rain
    312: 1.5,  # heavy intensity drizzle rain
    313: 2.0,  # shower rain and drizzle
    314: 3.0,  # heavy shower rain and drizzle
    321: 3.0,  # shower drizzle
    500: 0.3,  # light rain
    501: 1.0,  # moderate rain
    502: 2.0,  # heavy intensity rain
    503: 3.0,  # very heavy rain
    504: 4.0,  # extreme rain
    511: 5.0,  # freezing rain
    520: 2.0,  # light intensity shower rain
    521: 3.0,  # shower rain
    522: 4.0,  # heavy intensity shower rain
    531: 4.0,  # ragged shower rain
    611: 0.1,  # sleet
    612: 0.2,  # shower sleet
    615: 0.5,  # light rain and snow
    616: 1.0,  # rain and snow
    620: 0.5,  # light shower snow
}

class WeatherSensor(Sensor):
    LOOP_DELAY = 60
    NAME = 'WEATHER'

    # Forecast has data for every 3 hours, so let'sconsider only 12 hours
    RAIN_ITEMS_TO_MEASURE = 4

    def __init__(self, city_id=2654675):
        super(WeatherSensor, self).__init__()
        self.city_id = city_id

    def get_rain_forecast(self):
        response = requests.get(
            'http://api.openweathermap.org/data/2.5/forecast',
            params={
                'id': self.city_id,
                'appid': WEATHER_API_KEY,
            },
        )

        items = response.json()['list']
        items = items[:self.RAIN_ITEMS_TO_MEASURE]

        sum = 0
        for item in items:
            weather_id = item['weather'][0]['id']
            sum += WEATHER_CODE_RAIN_WEIGHTS.get(weather_id, 0)

        return float(sum) / self.RAIN_ITEMS_TO_MEASURE

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
        self.set_value('temperature', data['main']['temp'] - 273.15)
        self.set_value('pressure', data['main']['pressure'])
        self.set_value('icon_url', 'http://openweathermap.org/img/w/%s.png' % data['weather'][0]['icon'])
        self.set_value('rain_forecast_rating', self.get_rain_forecast())


weather = WeatherSensor()
weather.start()


@app.route('/sensors/weather/read')
def read_weather_values():
    return json.dumps({
        'status': 'ok',
        'data': {
            'humidity': weather.get_value('humidity'),
            'temperature': weather.get_value('temperature'),
            'pressure': weather.get_value('pressure'),
            'icon_url': weather.get_value('icon_url'),
            'rain_forecast_rating': weather.get_value('rain_forecast_rating'),
        },
    })
