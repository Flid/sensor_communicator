# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import logging
import time
from RF24 import *
import RPi.GPIO as GPIO

log = logging.getLogger(__name__)

RF24_PINS = [25, 8]
PAYLOAD_SIZE = 32
CHANNEL = 0x30
RETRIES_DELAY = 5
RETRIES_COUNT = 15

BASE_SEND_ADDR = 0x53654e6400
BASE_RECV_ADDR = 0x5265437600


DEVICES = {
    1: {
        'listen_pipe': 0x01,
        'send_pipe': 0x01,
        'pipe_number': 1,
    },
}


def init():
    global radio

    radio = RF24(*RF24_PINS)
    radio.begin()
    radio.setRetries(RETRIES_DELAY, RETRIES_COUNT)

    radio.setPALevel(RF24_PA_HIGH)
    radio.setDataRate(RF24_250KBPS)
    radio.setChannel(CHANNEL)

    # Open needed listening pipes for all devices.
    for device_id, device_info in DEVICES.iteritems():
        pipe_number = device_info.get('pipe_number')

        if pipe_number is None:
            continue

        radio.openReadingPipe(
            pipe_number,
            BASE_RECV_ADDR | device_info['listen_pipe'],
        )

    radio.printDetails()


def read_data():
    """
    If there's some data available - read one message and return.
    Else return None.
    """
    if radio.available():
        payload = map(ord, radio.read(PAYLOAD_SIZE))
        log.debug(
            'Got payload size=%s value=`%s`',
            len(payload),
            payload,
        )

        return payload


def send_data(device_id, payload):
    log.debug('Now sending length %s', len(payload))
    device_info = DEVICES[device_id]
    send_pipe = BASE_SEND_ADDR | device_info['send_pipe']

    radio.stopListening()

    try:
        radio.openWritingPipe(send_pipe)
        return radio.write(payload)
    finally:
        radio.startListening()
