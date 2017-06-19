#
# config.py
#
# discord-analytics - Store Discord records for later analysis
# Copyright (c) 2017 Ammon Smith
#
# discord-analytics is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

import json

__all__ = [
    'check',
    'load_config',
    'DEFAULT_CONFIG',
]

DEFAULT_CONFIG = {
    'servers': [
        '181866934353133570',
        '273534239310479360',
    ],
}

def is_string_or_null(obj):
    return type(obj) == str or \
            obj is None

def is_string_list(obj):
    if type(obj) != list:
        return False

    for item in obj:
        if type(item) != str:
            return False
    return True

def check(cfg):
    try:
        if not is_string_list(cfg['servers']):
            return False
    except KeyError:
        return False
    else:
        return True

def load_config(fn):
    with open(fn, 'r') as fh:
        obj = json.load(fn)
    return config_check(obj), obj

