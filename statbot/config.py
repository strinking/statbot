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

from numbers import Number
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

    # pylint: disable=too-many-return-statements
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

        if not isinstance(cfg.get('logger'), dict):
            logger.warning("Populating configuration field 'logger' with defaults")
            cfg['logger'] = {
                'full-messages': False,
                'ignored-events': False,
            }

        if not isinstance(cfg['logger']['full-messages'], bool):
            logger.error("Configuration field 'logger.full-messages' is not a bool")
            return False
        if not isinstance(cfg['logger']['ignored-events'], bool):
            logger.error("Configuration field 'logger.ignored-events' is not a bool")
            return False

        if not isinstance(cfg.get('crawler'), dict):
            logger.error("Configuration field 'crawler' not an object")
            return False
        if not isinstance(cfg['crawler']['batch-size'], Number):
            logger.error("Configuration field 'crawler.batch-size' is not a number")
            return False
        if cfg['crawler']['batch-size'] <= 0:
            logger.error("Configuration field 'crawler.batch-size' is zero or negative")
            return False
        if not isinstance(cfg['crawler']['yield-delay'], Number):
            logger.error("Configuration field 'crawler.yield-delay' is not a number")
            return False
        if cfg['crawler']['yield-delay'] <= 0:
            logger.error("Configuration field 'crawler.yield-delay' is zero or negative")
            return False
        if not isinstance(cfg['crawler']['empty-source-delay'], Number):
            logger.error("Configuration field 'crawler.empty-source-delay' is not a number")
            return False
        if cfg['crawler']['empty-source-delay'] <= 0:
            logger.error("Configuration field 'crawler.empty-source-delay' is zero or negative")
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
