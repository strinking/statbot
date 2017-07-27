#
# config.py
#
# statbot - Store Discord records for later analysis # Copyright (c) 2017 Ammon Smith
#
# statbot is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

import json

from .util import null_logger

__all__ = [
    'check',
    'load_config',
]

def is_string_or_null(obj):
    '''
    Determines if the given object
    is of type str or is None.
    '''

    return isinstance(obj, str) or obj is None

def is_int_list(obj):
    if not isinstance(obj, list):
        return False

    for item in obj:
        if not isinstance(item, int):
            return False
    return True

def is_string_list(obj):
    if not isinstance(obj, list):
        return False

    for item in obj:
        if not isinstance(item, str):
            return False
    return True

def check(cfg, logger=null_logger):
    '''
    Determines if the given dictionary has
    the correct fields and types.
    '''

    try:
        if not is_int_list(cfg['guilds']):
            logger.error("Configuration field 'guilds' is not an int list")
            return False
        if not isinstance(cfg['token'], str):
            logger.error("Configuration field 'token' is not a string")
            return False
        if not isinstance(cfg['url'], str):
            logger.error("Configuration field 'url' is not a string")
            return False
    except KeyError as err:
        logger.error(f"Configuration missing field: {err}")
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
