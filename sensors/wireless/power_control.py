# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from .base import Node, Message, State
from .utils import from_string_bool


class PowerControlMessage(Message):
    TYPE_ON = 255
    TYPE_OFF = 254


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
                from_string_bool(new['power_on']),
            )


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
        msg_type = self.MESSAGE_CLASS.TYPE_ON if is_enabled \
            else self.MESSAGE_CLASS.TYPE_OFF

        self.send_data(
            self.MESSAGE_CLASS(self.NODE_ID, msg_type),
        )
