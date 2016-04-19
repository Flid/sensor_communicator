# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from .base import Node, Message


class PowerControlMessage(Message):
    TYPE_ON = 255
    TYPE_OFF = 254


class PowerControlNode(Node):
    # We only allow one device of each type for now
    NODE_ID = 1
    MESSAGE_CLASS = PowerControlMessage
    NAME = 'lamp'

    LISTEN_PIPE_ADDR = 0x01
    SEND_PIPE_ADDR = 0x01
    LISTEN_PIPE_NUMBER = 1

    def set_state(self, is_enabled):
        msg_type = self.MESSAGE_CLASS.TYPE_ON if is_enabled \
            else self.MESSAGE_CLASS.TYPE_OFF

        self.send_data(
            self.MESSAGE_CLASS(self.NODE_ID, msg_type),
        )
