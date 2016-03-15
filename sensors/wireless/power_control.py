# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from .base import Node, Message


class PowerControlMessage(Message):
    FIELD_NAMES = {
        0: 'on',  # Turn power on/off
    }


class PowerControlNode(Node):
    # We only allow one device of each type for now
    NODE_ID = 1
    MESSAGE_CLASS = PowerControlMessage
