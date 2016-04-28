# -*- coding: utf-8 -*-
from __future__ import unicode_literals


def to_bool(value):
    if isinstance(value, basestring):
        return value.lower() in ['1', 'y', 'yes', 'true']

    return bool(value)
