# -*- coding: utf-8 -*-
import json
import logging
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


class EndomondoSensor(Sensor):
    LOOP_DELAY = 60
    ERRORS_THRESHOLD = 2
    NAME = 'ENDOMONDO'
    EPOCH_START = datetime(2016, 1, 1, 0, 0, 0)

    def __init__(self):
        super(EndomondoSensor, self).__init__()
        self._auth_token = None
        self.client = None

    def _get_workouts_history(self, after=None, prev_distance=0):
        if not after:
            after = self.EPOCH_START

        last_dt = None
        total_distance = prev_distance
        before = None
        maxResults = 100

        while True:
            log.debug('Getting workouts before %s', before)
            workouts = self.client.get_workouts(maxResults=maxResults, before=before)

            if not workouts:
                break

            if not last_dt:
                last_dt = workouts[0].start_time

            for w in workouts:
                if w.start_time <= after:
                    break

                total_distance += w.distance
            else:
                # Need more workouts
                before = workouts[-1].start_time
                continue

            # All workouts are parsed, exiting
            break

        return {'last_dt': last_dt, 'total_distance': total_distance}

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
        )
        cache.set_value('workouts_history', actual_data)

        self.set_value('total_distance', actual_data['total_distance'])

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

        },
    })


@app.route('/sensors/endomondo/invalidate_cache')
def invalidate_endomondo_cache():
    endomondo.invalidate_cache()
    endomondo._iteration()

    return json.dumps({
        'status': 'ok',
    })
