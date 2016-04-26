# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import logging
import json

from app import app
from flask import request
from .base import wireless_sensor

logger = logging.getLogger(__name__)


@app.route('/sensors/wireless/<name>/state', methods=['GET', 'POST'])
def read_wireless_sensors(name):
    node = wireless_sensor.get_node(name=name)
    if not node:
        return json.dumps({
            'status': 'error',
            'error_code': 'node_not_found',
        })

    if request.method == 'GET':

        return json.dumps({
            'status': 'ok',
            'is_online': node.state is not None,
            'state': node.state.data if node.state else None,
        })

    else:
        if node.state is None:
            return json.dumps({
                'status': 'error',
                'error_code': 'offline',
            })

        node.state.update(request.form)

        return json.dumps({'status': 'ok'})

