# -*- coding: utf-8 -*-
from threading import Thread, Lock
import logging
from time import sleep
from db import conn_pool
import json

from psycopg2 import Error as PsycopgError
from app import app

from .socket_server import server as SServer

log = logging.getLogger(__name__)


class SensorError(Exception):
    pass


class Sensor(object):
    STATUS_ERROR = 'error'
    STATUS_OK = 'ok'
    STATUS_IDLE = 'idle'

    LOOP_DELAY = 1
    ERRORS_THRESHOLD = 10
    DB_ENABLED = False
    NAME = '<NoName>'
    _active_sensors = []

    def __init__(self):
        self.should_stop = False
        self._errors_count = 0
        self._lock = Lock()
        self.thread = Thread(target=self._loop)
        self._data = {}
        self._conn = None

        self.set_value('status', self.STATUS_IDLE)

    def start(self):
        log.info('Starting sensor %s', self.NAME)
        Sensor._active_sensors.append(self)
        self.should_stop = False
        self.thread.start()

    def stop(self):
        log.info('Stopping sensor %s', self.NAME)
        self.should_stop = True
        Sensor._active_sensors.remove(self)
        self.set_value('status', self.STATUS_IDLE)

    @staticmethod
    def stop_all():
        log.info('Stopping all the sensors...')
        while Sensor._active_sensors:
            sensor = Sensor._active_sensors[-1]
            sensor.stop()

    def _iteration(self):
        raise NotImplementedError()

    def _get_value(self, key):
        return self._data.get(key)

    def _set_value(self, key, value):
        self._data[key] = value

    def get_value(self, *args, **kwargs):
        self._lock.acquire()
        try:
            return self._get_value(*args, **kwargs)
        finally:
            self._lock.release()

    def set_value(self, key, value):
        self._lock.acquire()
        try:
            self._set_value(key, value)
        finally:
            self._lock.release()

    @staticmethod
    def by_name(name):
        for sensor in Sensor._active_sensors:
            if sensor.NAME == name:
                return sensor

    def process_message(self, data):
        """
        By default all messages are just ignored
        """

    def _process_socket_messages(self):
        for sensor_name, data, fno in SServer.get_messages():
            sensor = Sensor.by_name(sensor_name)

            if not sensor:
                log.warning('Socket message for unexpected sensor %s', sensor_name)
                continue

            try:
                response = sensor.process_client_message(data)

                if response is None:
                    return

                if not isinstance(response, basestring):
                    response = json.dumps(response)

                SServer.send_message(response, fno)
            except Exception as ex:
                log.warning('Error while processing socket message:', exc_info=ex)

    def _loop(self):
        while True:
            try:
                self._iteration()
                self.errors_count = 0
                self.set_value('status', self.STATUS_OK)
            except Exception as ex:
                if isinstance(ex, SensorError):
                    log.error(
                        'Error getting %s sensor data: %s' % (self.__class__, ex),
                    )
                else:
                    log.error('Unexpected exception.', exc_info=ex)

                self._errors_count += 1
                if self.ERRORS_THRESHOLD and self._errors_count >= self.ERRORS_THRESHOLD:
                    self.set_value('status', self.STATUS_ERROR)
            finally:
                if self.LOOP_DELAY < 1:
                    num, t = 1, self.LOOP_DELAY
                else:
                    num, t = int(self.LOOP_DELAY), 1

                for _ in xrange(num):
                    if self.should_stop:
                        return
                    sleep(t)

    def db_execute(self, command):
        if not self._conn:
            self._conn = conn_pool.getconn()

        try:
            cur = self._conn.cursor()
            cur.execute(command)
            cur.commit()
        except PsycopgError as ex:
            log.error('Error while executing request %s: %s', command, ex)
            self._conn.rollback()


@app.route('/sensors/list')
def list_sensors():
    sensors = []
    for s in Sensor._active_sensors:
        sensors.append({
            'name': s.NAME,
            'loop_delay': s.LOOP_DELAY,
            'status': s.get_value('status'),
            'errors_count': s._errors_count,
            'errors_threshold': s.ERRORS_THRESHOLD,
        })

    return json.dumps({
        'status': 'ok',
        'data': sensors,
    })
