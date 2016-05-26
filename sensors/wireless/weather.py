# -*- coding: utf-8 -*-
"""
Wireless DHT22, measures temperature and humidity outdoors.
"""
from __future__ import unicode_literals

import logging

from .base import Node, Message, State
from .utils import to_bool


logger = logging.getLogger(__name__)


class WeatherState(State):
    @classmethod
    def _parse_raw_data(cls, raw_data):
        return {
            'humidity': int(raw_data[1]),
            'temperature': int(raw_data[0] - 100),
        }


class WeatherMessage(Message):
    pass


class WeatherNode(Node):
    # We only allow one device of each type for now
    NODE_ID = 2
    MESSAGE_CLASS = WeatherMessage
    STATE_CLASS = WeatherState
    NAME = 'weather'

    # Weather sensor never reads data from this pipe,
    # but you can send something here, especially
    # if you are too lonely and have nobody else to talk to.
    SEND_PIPE_ADDR = 0x02

    LISTEN_PIPE_NUMBER = 2
    LISTEN_PIPE_ADDR = 0x02

    OFFLINE_AFTER_N_SECONDS = 3600
