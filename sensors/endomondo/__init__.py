# -*- coding: utf-8 -*-
import json
import logging
import time
from datetime import datetime

from beaker.cache import CacheManager
from beaker.util import parse_cache_config_options

from app import app
from ..base import Sensor
from prod_config import ENDOMONDO_EMAIL, ENDOMONDO_PASSWORD
from .client import MobileApi

log = logging.getLogger(__name__)

opts = {'cache.type': 'file', 'cache.file_dir': '.cache', 'cache.data_dir': '.cache'}
cache_manager = CacheManager(**parse_cache_config_options(opts))
cache = cache_manager.get_cache('endomondo_data', type='file', expire=3600*24)


def datetime_to_integer_unixtime(dt):
    """
    Converting from datetime type to unixtime
    """
    try:
        return int(time.mktime(dt.timetuple()))
    except AttributeError:  # pragma: no cover
        raise TypeError(
            'datetime_to_unixtime expects datetime object, got %s instead' % type(dt),
        )


class EndomondoSensor(Sensor):
    LOOP_DELAY = 600
    ERRORS_THRESHOLD = 2
    NAME = 'ENDOMONDO'
    EPOCH_START = datetime(2016, 1, 1, 0, 0, 0)

    def __init__(self):
        super(EndomondoSensor, self).__init__()

        self._auth_token = None
        self.client = None

    def _get_distance_by_day(self, workouts_log):
        distance_by_day = {}

        for unixtime, distance in workouts_log.items():
            date = datetime.fromtimestamp(int(unixtime)).date()
            key = date.strftime('%Y-%m-%d')

            if key not in distance_by_day:
                distance_by_day[key] = 0

            distance_by_day[key] += distance

        return distance_by_day

    def _get_workouts_history(self, after=None, prev_distance=0,
                              last_workout_distance=0, workouts_log=None):
        if not after:
            after = self.EPOCH_START

        last_dt = None
        total_distance = prev_distance
        last_distance = 0
        before = None
        maxResults = 100

        # TODO - filter out too old records
        workouts_log = workouts_log or {}

        while True:
            log.debug('Getting workouts before %s', before)
            workouts = self.client.get_workouts(maxResults=maxResults, before=before)

            if not workouts:
                break

            if not last_dt:
                last_dt = workouts[0].start_time
                last_distance = workouts[0].distance

            for w in workouts:
                if w.start_time < after:
                    break

                # Keys in JSON dicts should be strings
                start_unixtime = str(datetime_to_integer_unixtime(w.start_time))

                if w.start_time == after:
                    # Update the last record, it could have been changed.
                    # It happens when we read data during actual workout.

                    total_distance -= last_workout_distance

                total_distance += w.distance

                workouts_log[start_unixtime] = w.distance
            else:
                # Need more workouts
                before = workouts[-1].start_time
                continue

            # All workouts are parsed, exiting
            break

        return {
            'last_dt': last_dt,
            'last_distance': last_distance,
            'total_distance': total_distance,
            'workouts_log': workouts_log,
            'distance_by_day': self._get_distance_by_day(workouts_log),
        }

    def _iteration(self):
        if not self._auth_token:
            _client = MobileApi(email=ENDOMONDO_EMAIL, password=ENDOMONDO_PASSWORD)
            self._auth_token = _client.get_auth_token()

        self.client = MobileApi(auth_token=self._auth_token)
        history = cache.get(key='workouts_history', createfunc=self._get_workouts_history)
        log.info('History found: %s', history)

        actual_data = self._get_workouts_history(
            after=history['last_dt'],
            prev_distance=history['total_distance'],
            last_workout_distance=history['last_distance'],
            workouts_log=history['workouts_log'],
        )
        cache.set_value('workouts_history', actual_data)

        self.set_value('total_distance', actual_data['total_distance'])
        self.set_value('distance_by_day', actual_data['distance_by_day'])

    def invalidate_cache(self):
        cache.clear()


endomondo = EndomondoSensor()
endomondo.start()


@app.route('/sensors/endomondo/read')
def read_endomondo_values():
    return json.dumps({
        'status': 'ok',
        'data': {
            'total_distance': endomondo.get_value('total_distance'),
            'distance_by_day': endomondo.get_value('distance_by_day'),
        },
    })


@app.route('/sensors/endomondo/invalidate_cache')
def invalidate_endomondo_cache():
    endomondo.invalidate_cache()
    endomondo._iteration()

    return json.dumps({
        'status': 'ok',
    })
