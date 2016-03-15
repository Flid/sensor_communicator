import requests
import json
import logging

from app import app
from prod_config import WEATHER_API_KEY
from .base import Sensor

log = logging.getLogger(__name__)

# There are lots of possible rain types, let's get value to each,
# assuming that 1 is a usual rain

LIGHT_RAIN = 0.2
RAIN = 1.0
HEAVY_RAIN = 2.0
DRIZZLE = 0.7


WEATHER_CODE_RAIN_WEIGHTS = {
    200: LIGHT_RAIN,            # thunderstorm with light rain
    201: RAIN,                  # thunderstorm with rain
    202: HEAVY_RAIN,            # thunderstorm with heavy rain
    230: LIGHT_RAIN * DRIZZLE,  # thunderstorm with light drizzle
    231: RAIN * DRIZZLE,        # thunderstorm with drizzle
    232: HEAVY_RAIN * DRIZZLE,  # thunderstorm with heavy drizzle
    300: LIGHT_RAIN * DRIZZLE,  # light intensity drizzle
    301: RAIN * DRIZZLE,        # drizzle
    302: HEAVY_RAIN * DRIZZLE,  # heavy intensity drizzle
    310: LIGHT_RAIN,            # light intensity drizzle rain
    311: RAIN,                  # drizzle rain
    312: HEAVY_RAIN,            # heavy intensity drizzle rain
    313: RAIN,                  # shower rain and drizzle
    314: HEAVY_RAIN,            # heavy shower rain and drizzle
    321: RAIN * DRIZZLE,        # shower drizzle
    500: LIGHT_RAIN,            # light rain
    501: RAIN,                  # moderate rain
    502: HEAVY_RAIN,            # heavy intensity rain
    503: HEAVY_RAIN * 2,        # very heavy rain
    504: HEAVY_RAIN * 4,        # extreme rain
    511: HEAVY_RAIN * 4,        # freezing rain
    520: LIGHT_RAIN,            # light intensity shower rain
    521: RAIN,                  # shower rain
    522: HEAVY_RAIN,            # heavy intensity shower rain
    531: HEAVY_RAIN,            # ragged shower rain
    611: RAIN,                  # sleet
    612: RAIN,                  # shower sleet
    615: LIGHT_RAIN,            # light rain and snow
    616: RAIN,                  # rain and snow
    620: LIGHT_RAIN,            # light shower snow
}


class WeatherSensor(Sensor):
    LOOP_DELAY = 60
    ERRORS_THRESHOLD = 2
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
