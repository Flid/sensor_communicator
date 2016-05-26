# -*- coding: utf-8 -*-
import logging
from time import time
import socket
import json
from threading import Lock

from RF24 import RF24_PA_MAX, RF24_PA_HIGH, RF24_250KBPS, RF24
import RPi.GPIO as GPIO

from ..base import Sensor, SensorError
from ..socket_server import server as SServer

log = logging.getLogger(__name__)


class State(object):
    """
    "Wireless" is a special type of sensor, which works with NRF24L01+ wireless sensor
    attached. It provides an abstraction for wireless devices connected, allowing to
    send them messages and receive their current states.
    """

    ALLOWED_KEYS = set()

    def __init__(self, node, data=None, is_online=True):
        self.node = node
        self.data = data
        self.is_online = is_online

    @classmethod
    def _parse_raw_data(cls, raw_data):
        return {}

    @classmethod
    def from_message(cls, node, msg):
        assert msg.msg_type == Message.TYPE_STATUS

        data = cls._parse_raw_data(msg.data)
        log.info('Parsed state %s', data)
        return cls(node=node, data=data)

    def _apply_new_state(self, old, new):
        pass

    def update(self, data):
        data = {k: v for k, v in data.iteritems() if k in self.ALLOWED_KEYS}
        self._apply_new_state(self.data, data)
        self.data.update(data)

    def render_to_response(self):
        return {
            'sensor': self.node.sensor.NAME,
            'node_id': self.node.NODE_ID,
            'msg_stream': str(self.node.NODE_ID),
            'is_online': self.is_online,
            'type': 'state',
            'state': self.data,
        }

    def send_update_message(self):
        SServer.send_broadcast_message(
            self.render_to_response(),
            self.node.sensor.NAME,
            str(self.node.NODE_ID),
        )

    def __eq__(self, other):
        if not isinstance(other, State):
            return False

        return self.data == other.data and self.node == other.node

    def __ne__(self, other):
        return not self.__eq__(other)


class Message(object):
    """
    A representation of a bytestring being sent to/from wireless device.
    Helps to parse or format a message.
    """
    MAX_DATA_LEN = 31  # Max payload size one byte for message type

    # Send every N seconds. After M times without response node gows offline.
    TYPE_STATUS = 0
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

    @classmethod
    def parse(cls, raw_data):
        node_id = raw_data[0]
        msg_type = raw_data[1]
        data = raw_data[2:]

        msg = cls(node_id, msg_type)

        if msg_type == cls.TYPE_STATUS:
            msg.data = data
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
        data = chr(self.msg_type)

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
    """
    Node represents a single wireless device with its own ID and hardware address.
    It helps to communicate with a single the device directly.
    """
    NODE_ID = None
    LISTEN_PIPE_ADDR = None
    LISTEN_PIPE_NUMBER = None
    SEND_PIPE_ADDR = None

    # If we do not have status update for more then N
    # seconds in a row - it's offline for us.
    OFFLINE_AFTER_N_SECONDS = 20

    MESSAGE_CLASS = Message
    STATE_CLASS = State

    PAYLOAD_SIZE = 32
    BASE_SEND_ADDR = 0x53654e6400
    BASE_RECV_ADDR = 0x5265437600

    SEND_RETRIES = 5
    SEND_DELAY = 50  # msec

    def __init__(self, sensor, radio):
        log.info('Initializing wireless node %s', self.__class__.__name__)
        self._fields = {}
        self._errors_in_a_row = 0
        self._last_status_update_time = time()
        self._radio = radio
        self.sensor = sensor
        self.state = self.STATE_CLASS(self, is_online=False)

        if self.LISTEN_PIPE_NUMBER is not None:
            log.info(
                'Start listening on pipe %s addr=%s',
                self.LISTEN_PIPE_NUMBER,
                self.recv_addr,
            )
            radio.openReadingPipe(
                self.LISTEN_PIPE_NUMBER,
                self.recv_addr,
            )

    @property
    def recv_addr(self):
        return self.BASE_RECV_ADDR | self.LISTEN_PIPE_ADDR

    @property
    def send_addr(self):
        return self.BASE_SEND_ADDR | self.SEND_PIPE_ADDR

    @property
    def name(self):
        return self.__class__.__name__

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

    def _send_data_to_radio(self, payload):
        payload = bytearray(payload)
        log.debug('%s: Sending length %s', self.name, len(payload))
        try:
            self._radio.stopListening()
            self._radio.openWritingPipe(self.send_addr)
            if not self._radio.write(payload):
                raise SensorError('Failed to send data to %s' % self.name)
        finally:
            self._radio.startListening()

    def send_data(self, msg):
        for i in range(self.SEND_RETRIES):
            try:
                self._send_data_to_radio(msg.format())
                break
            except SensorError as ex:
                log.warning(
                    '[%s/%s] Error sending message %s to device %s: %s',
                    i + 1,
                    self.SEND_RETRIES,
                    msg,
                    self.NODE_ID,
                    str(ex),
                )
        else:
            raise SensorError(
                'Request failed %s times in a row' % self.SEND_RETRIES,
            )

    def check_if_offline(self):
        if not self.state.is_online:
            return

        if time() - self._last_status_update_time < self.OFFLINE_AFTER_N_SECONDS:
            # Everything's fine
            return
        self.state = self.STATE_CLASS(self, is_online=False)
        log.info('Device `%s` went offline', self.name)
        self.state.send_update_message()

    def process_new_hw_message(self, msg):
        log.debug(
            'Received HW message of type %s, data %s'
            % (msg.msg_type, map(int, msg.data)),
        )

        if msg.msg_type == self.MESSAGE_CLASS.TYPE_STATUS:
            new_state = self.STATE_CLASS.from_message(self, msg)

            if new_state != self.state:
                self.state = new_state
                new_state.send_update_message()

            self._last_status_update_time = time()

        if msg.msg_type == self.MESSAGE_CLASS.TYPE_FIELD_RESPONSE:
            self._fields[msg.field_name] = msg.data

    def process_client_message(self, data):
        t = data['type']

        if t == 'get_state':
            return self.state.render_to_response()

        if t == 'set_state':
            self.state.update(data.get('state'))
            self.state.send_update_message()
            return

        return {'error': 'unknown message type %s' % t}

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
    NAME = 'nrf24l01'
    LOOP_DELAY = 0.1
    ERRORS_THRESHOLD = None

    RF24_PINS = [25, 8]
    CHANNEL = 0x30
    RETRIES_DELAY = 5
    RETRIES_COUNT = 15
    MAX_PAYLOAD_SIZE = 32

    def __init__(self):
        super(WirelessSensor, self).__init__()
        log.info('INIT1')
        from .power_control import PowerControlNode
        from .weather import WeatherNode

        self._node_by_id = {
            PowerControlNode.NODE_ID: PowerControlNode,
            WeatherNode.NODE_ID: WeatherNode,
        }
        self._active_nodes = {}

        self._radio = self._get_radio()
        self._init_nodes()

    def get_node(self, node_id=None, name=None):
        if node_id is not None:
            return self._active_nodes.get(node_id)

        for node in self._active_nodes.itervalues():
            if node.NAME == name:
                return node

    def _get_radio(self):
        log.info('Initializing radio...')
        radio = RF24(*self.RF24_PINS)
        radio.begin()
        radio.setRetries(self.RETRIES_DELAY, self.RETRIES_COUNT)

        radio.setPALevel(RF24_PA_HIGH)
        radio.setDataRate(RF24_250KBPS)
        radio.setChannel(self.CHANNEL)
        radio.printDetails()
        radio.startListening()

        return radio

    def _init_nodes(self):
        """
        Open needed listening pipes for all devices.
        """
        for node_id, node_cls in self._node_by_id.iteritems():
            self._active_nodes[node_id] = node_cls(self, self._radio)

    def _read_data_from_radio(self):
        """
        If there's some data available - read one message and return.
        Else return None.
        """
        if self._radio.available():
            payload = self._radio.read(self.MAX_PAYLOAD_SIZE)

            log.debug(
                'Got payload size=%s value=%s',
                len(payload),
                map(int, payload),
            )

            return payload

    def process_client_message(self, data):
        node_id = data.get('node_id')
        type_ = data.get('type')

        if node_id is None or not type_:
            return {'error': 'bad format'}

        node = self.get_node(node_id=node_id)

        if not node:
            return {'error': 'node not found'}

        return node.process_client_message(data)

    def _process_hw_messages(self):
        while True:
            new_msg = self._read_data_from_radio()
            if not new_msg:
                break

            node_id = int(new_msg[0])
            node = self._active_nodes.get(node_id)

            if not node:
                log.warning('Message for unknown node_id=%s' % node_id)
                continue

            node.process_new_hw_message(
                node.MESSAGE_CLASS.parse(new_msg),
            )

    def _iteration(self):
        """
        Read all new messages and route them to nodes.
        """
        self._process_hw_messages()


        # Check devices state
        for node in self._active_nodes.itervalues():
            node.check_if_offline()

        self._process_socket_messages()




wireless_sensor = WirelessSensor()
wireless_sensor.start()

