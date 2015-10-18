# -*- coding: utf-8 -*-
import logging
import atexit

from app import app

from sensors.base import Sensor
logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)


@atexit.register
def goodbye():
    logging.info('Shutting down...')
    Sensor.stop_all()


app.run(
    host='127.0.0.1',
    port=10100,
)
