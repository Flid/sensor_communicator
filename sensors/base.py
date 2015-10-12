# -*- coding: utf-8 -*-
from threading import Thread, Lock
import logging
from time import sleep

log = logging.getLogger(__name__)


class SensorError(Exception):
    pass


class Sensor(object):
    ERROR_VALUE = 'ERROR'
    LOOP_DELAY = 1
    ERRORS_THRESHOLD = 10
    _active_sensors = []

    def __init__(self):
        self.should_stop = False
        self._errors_count = 0
        self._lock = Lock()
        self.thread = Thread(target=self._loop)
        self._data = {}

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
