# -*- coding: utf-8 -*-

"""
Simple class, that works with DHT22 temperature/humidity sensor.
"""

import logging
import json

from app import app
from .base import Sensor, SensorError

try:
    import Adafruit_DHT
except ImportError:
    # Used mainly for testing
    from mock import Mock
    Adafruit_DHT = Mock(read=Mock(return_value=(None, None)))

log = logging.getLogger(__name__)


class DHT22(Sensor):
    LOOP_DELAY = 60
    NAME = 'DHT22'

    def __init__(self, gpio_number=24):
        super(DHT22, self).__init__()
        self.gpio_number = gpio_number

    def _iteration(self):
        humidity, temperature = Adafruit_DHT.read(
            Adafruit_DHT.DHT22,
            self.gpio_number,
        )

        if humidity is None or temperature is None:
            raise SensorError()

        self.set_value('humidity', humidity)
        self.set_value('temperature', temperature)


dht22 = DHT22()
dht22.start()


@app.route('/sensors/dht22/read')
def read_dht22_values():
    return json.dumps({
        'status': 'ok',
        'data': {
            'humidity': dht22.get_value('humidity'),
            'temperature': dht22.get_value('temperature'),
        },
    })
