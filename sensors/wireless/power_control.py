# -*- coding: utf-8 -*-
"""
Simple wireless device, that can be turned on/off remotely.
"""
from __future__ import unicode_literals

import logging

from .base import Node, Message, State
from .utils import to_bool


logger = logging.getLogger(__name__)


class PowerControlState(State):
    ALLOWED_KEYS = {'power_on'}

    @classmethod
    def _parse_raw_data(cls, raw_data):
        return {
            'power_on': raw_data[0],
        }

    def _apply_new_state(self, old, new):
        if 'power_on' in new:
            self.node.set_power_state(
                to_bool(new['power_on']),
            )


class PowerControlMessage(Message):
    TYPE_ON = 255
    TYPE_OFF = 254


class PowerControlNode(Node):
    # We only allow one device of each type for now
    NODE_ID = 1
    MESSAGE_CLASS = PowerControlMessage
    STATE_CLASS = PowerControlState
    NAME = 'lamp'

    LISTEN_PIPE_ADDR = 0x01
    SEND_PIPE_ADDR = 0x01
    LISTEN_PIPE_NUMBER = 1

    def set_power_state(self, is_enabled):
        logger.info('Setting power state to %s', is_enabled)
        msg_type = self.MESSAGE_CLASS.TYPE_ON if is_enabled \
            else self.MESSAGE_CLASS.TYPE_OFF

        self.send_data(
            self.MESSAGE_CLASS(self.NODE_ID, msg_type),
        )
