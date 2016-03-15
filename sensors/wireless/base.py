# -*- coding: utf-8 -*-
import logging

from ..base import Sensor, SensorError
from .hw_communications import (
    init as init_hw,
    read_data,
    send_data,
)

log = logging.getLogger(__name__)


class Message(object):
    MAX_DATA_LEN = 31  # Max payload size one byte for message type

    # Send every N seconds. After M times without response, terminate the node.
    TYPE_PING = 0
    # Asking for a value of the field. Field id should be passed in data.
    TYPE_FIELD_REQUEST = 1
    # Set some value of the field. Should be followed by field id and actual value.
    TYPE_FIELD_SET = 2
    # Response for TYPE_DATA_REQUEST
    TYPE_FIELD_RESPONSE = 3
    # Ask device to proxy data to another device in the next lavel
    TYPE_PROXY = 4
    # Other types are device-specific.

    FIELD_NAMES = {}  # Number to name map

    def __init__(self, node_id, msg_type, data=None, field_name=None):
        self.node_id = node_id
        self.msg_type = msg_type
        self.field_name = field_name
        self.data = data

    @property
    def field_id(self):
        # TODO: optimize
        _field_numbers = {v: k for k, v in self.FIELD_NAMES}
        return _field_numbers[self.field_name]

    @staticmethod
    def parse_header(header_byte):
        """
        return (node_id, type)
        """
        if isinstance(header_byte, basestring):
            assert len(header_byte) == 1
            header_byte = ord(header_byte)

        return header_byte % 8, header_byte / 8

    def format_header(self):
        assert 0 <= self.node_id < 8
        return chr(self.node_id + self.msg_type * 8)

    @classmethod
    def parse(cls, raw_data):
        node_id, msg_type = Message.parse_header(raw_data[0])
        msg_type = ord(raw_data[0])
        data = raw_data[1:]

        msg = cls(node_id, msg_type)

        if msg_type == cls.TYPE_PING:
            return msg

        elif msg_type == cls.TYPE_FIELD_RESPONSE:
            msg.field_name = cls.FIELD_NAMES.get(ord(data[0]))
            if not msg.field_name:
                raise SensorError('Unknown field_id %s', ord(data[0]))

            msg.data = data[1:]
        else:
            raise SensorError('Unexpected message type: ' + str(msg_type))

        return msg

    def format(self):
        data = self.format_header()

        if self.msg_type == self.TYPE_FIELD_REQUEST:
            data += chr(self.field_id)

        elif self.msg_type == self.TYPE_FIELD_SET:
            data += chr(self.field_id) + self.data

        return data

    def __repr__(self):
        return '<%s msg_type=%s, field_name=%s, data_len=%s' % (
            self.__class__.__name__,
            self.msg_type,
            self.field_name,
            len(self.data) if self.data else 'None',
        )


class Node(object):
    STATE_ONLINE = 'online'
    STATE_OFFLINE = 'offline'
    NODE_ID = None

    PING_EVERY_N_LOOPS = 10
    # Once we are about to send Nth ping in a row without response - give up.
    TERMINATE_AFTER_N_ERRORS = 5

    MESSAGE_CLASS = Message

    def __init__(self):
        self.state = self.STATE_ONLINE
        self._fields = {}
        self._errors_in_a_row = 0
        self._lops_without_pings_left = 0

    def get_value(self, field_name):
        return self._fields.get(field_name)

    def ask_for_value(self, field_name):
        self.send_data(
            self.MESSAGE_CLASS(
                self.NODE_ID,
                self.MESSAGE_CLASS.TYPE_FIELD_REQUEST,
                field_name=field_name,
            ),
        )

    def set_value(self, field_name, value):
        self.send_data(
            self.MESSAGE_CLASS(
                self.NODE_ID,
                self.MESSAGE_CLASS.TYPE_FIELD_SET,
                data=value,
                field_name=field_name,
            ),
        )

    def _send_data(self, data_bytes):
        """
        Actual low-level data sending.
        """
        raise NotImplementedError()

    def send_data(self, msg):
        try:
            self._send_data(msg.format())
            self._errors_in_a_row = 0
        except SensorError as ex:
            log.error(
                'Error sending message %s to device %s: %s',
                msg,
                self.NODE_ID,
                str(ex),
            )
            self._state = self.STATE_OFFLINE

            self._errors_in_a_row += 1

            if self._errors_in_a_row == self.TERMINATE_AFTER_N_ERRORS:
                self.state = self.STATE_OFFLINE
                raise SensorError(
                    'Request failed %s times in a row' % self.TERMINATE_AFTER_N_ERRORS,
                )

    def send_ping(self):
        self._lops_without_pings_left += 1
        if self._lops_without_pings_left < self.PING_EVERY_N_LOOPS:
            return

        self._lops_without_pings_left = 0

        self.send_data(
            self.MESSAGE_CLASS(
                self.NODE_ID,
                msg_type=self.MESSAGE_CLASS.TYPE_PING,
            ),
        )

    def process_new_message(self, raw_bytes):
        msg = self.MESSAGE_CLASS.parse(raw_bytes)

        if msg.msg_type == self.MESSAGE_CLASS.TYPE_FIELD_RESPONSE:
            self._fields[msg.field_name] = msg.data

    def terminate(self):
        """
        Can be used to do something before dying, like sending message to the device.
        """


class WirelessSensor(Sensor):
    """
    The process starts with sensor connecting to the HUB and
    sending hello message with it's identifier.
    When it happens, we create a node and route all message to it later.
    """
    LOOP_DELAY = 1
    ERRORS_THRESHOLD = None

    def __init__(self):
        super(Sensor, self).__init__()

        from .power_control import PowerControlNode

        self._node_by_id = {
            PowerControlNode.NODE_ID: PowerControlNode,
        }
        self._active_nodes = {}

        init_hw()

    def _get_or_create_node(self, node_id):
        node = self._active_nodes.get(node_id)

        if node is None or node.state == Node.STATE_ONLINE:
            node_cls = self._node_by_id.get(node_id)

            if not node_cls:
                log.error('Node %s not found, skipping.', node_id)
                raise SensorError()

            node = node_cls()
            self._active_nodes[node_id] = node

        return node

    def _terminate_node(self, node_id):
        node = self._active_nodes.get(node_id)
        if not node:
            return

        if node.state != Node.STATE_OFFLINE:
            node.terminate()

        self._active_nodes.pop(node_id, None)

    def _cleanup_node(self, node_id):
        """
        If node is offline - remove it from actives.
        """
        node = self._active_nodes.get(node_id)
        if node.state == Node.STATE_OFFLINE:
            self._active_nodes.pop(node_id, None)

    def _iteration(self):
        """
        Read all new messages and route them to nodes.
        """

        while True:
            new_msg = read_data()
            if not new_msg:
                break

            node_id, msg_type = Message.parse_header(ord(new_msg[0]))

            try:
                node = self._get_or_create_node(node_id)
                node.process_new_message(new_msg)
            except Exception as ex:
                if isinstance(ex, SensorError):
                    # Message should already be logged
                    self._cleanup_node(node_id)
                else:
                    log.exception('Error wile processing message.')
                    self._terminate_node(node_id)

                continue

        # Ping all devices if needed
        for node in self._active_nodes:
            try:
                node.send_ping()
            except SensorError as ex:
                log.error(str(ex))
                node.terminate()
