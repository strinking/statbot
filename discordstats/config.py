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
]

def is_string_or_null(obj):
    '''
    Determines if the given object
    is of type str or is None.
    '''

    return type(obj) == str or \
            obj is None

def is_string_list(obj):
    '''
    Determines if the given object
    is a list of strings.
    '''

    if type(obj) != list:
        return False

    for item in obj:
        if type(item) != str:
            return False
    return True

class _NullLogger:
    def error(*args, **kwargs):
        pass

null_logger = _NullLogger()

def check(cfg, logger=null_logger):
    '''
    Determines if the given dictionary has
    the correct fields and types.
    '''

    try:
        if not is_string_list(cfg['servers']):
            logger.error("Configuration lacks 'servers', a string list")
            return False
        if type(cfg['token']) != str:
            logger.error("Configuration lacks 'token', a string")
            return False
        if type(cfg['url']) != str:
            logger.error("Configuration lacks 'url', a string")
            return False
    except KeyError:
        return False
    else:
        return True

def load_config(fn, logger=null_logger):
    '''
    Loads a JSON config from the given file.
    This returns a tuple of the object and whether
    it is valid or not.
    '''

    with open(fn, 'r') as fh:
        obj = json.load(fh)
    return obj, check(obj, logger)

