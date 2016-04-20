# -*- coding: utf-8 -*-
from __future__ import unicode_literals


def from_string_bool(value):
    return value.lower() in ['1', 'y', 'yes', 'true']
