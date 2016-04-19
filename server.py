# -*- coding: utf-8 -*-
import logging
from logging.config import dictConfig
import atexit
import signal
import os

from app import app

from sensors.base import Sensor

dictConfig({
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': {
        'default': {
            'level': 'DEBUG',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'when': 'midnight',
            'backupCount': 7,
            'filename': '/var/log/sensors.log',
            'formatter': 'standard',
        },
    },
    'loggers': {
        '': {
            'handlers': ['default'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'urllib3': {
            'handlers': ['default'],
            'level': 'WARN',
            'propagate': False,
        },
        'requests': {
            'handlers': ['default'],
            'level': 'WARN',
            'propagate': False,
        },
    }
})

log = logging.getLogger()


@atexit.register
def on_exit():
    log.info('Exitting...')
    Sensor.stop_all()


def signal_hendler(*args, **kwargs):
    log.info('SIGINT received')
    on_exit()
    exit(1)


signal.signal(signal.SIGINT, signal_hendler)

app.run(
    host='0.0.0.0',
    port=10100,
)
