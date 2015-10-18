# -*- coding: utf-8 -*-
import logging
import signal
import json

from app import app

from sensors.base import Sensor
logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)


def sig_handler(signum, frame):
    logging.info('Shutting down...')
    Sensor.stop_all()
    exit()

signal.signal(signal.SIGINT, sig_handler)


app.run(
    host='127.0.0.1',
    port=10100,
)
