# -*- coding: utf-8 -*-
from threading import Thread, Lock
import logging
from time import sleep
from db import conn_pool
from psycopg2 import Error as PsycopgError

log = logging.getLogger(__name__)


class SensorError(Exception):
    pass


class Sensor(object):
    ERROR_VALUE = 'ERROR'
    LOOP_DELAY = 1
    ERRORS_THRESHOLD = 10
    DB_ENABLED = False
    _active_sensors = []

    def __init__(self):
        self.should_stop = False
        self._errors_count = 0
        self._lock = Lock()
        self.thread = Thread(target=self._loop)
        self._data = {}
        self._conn = None

    def start(self):
        Sensor._active_sensors.append(self)
        self.should_stop = False
        self.thread.start()

    def stop(self):
        self.should_stop = True
        Sensor._active_sensors.remove(self)

    @staticmethod
    def stop_all():
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

    def set_value(self, *args, **kwargs):
        self._lock.acquire()
        try:
            self._set_value(*args, **kwargs)
        finally:
            self._lock.release()

    def _loop(self):
        while True:
            if self.should_stop:
                return

            sleep(self.LOOP_DELAY)

            try:
                self._iteration()
            except SensorError as ex:
                log.error('Error getting %s sensor data: %s' % (self.__class__, ex))
                self._errors_count += 1
                if self._errors_count >= self.ERRORS_THRESHOLD:
                    self.set_value(self.ERROR_VALUE)
                continue

            self.errors_count = 0

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
