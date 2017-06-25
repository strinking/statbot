#
# util.py
#
# discord-analytics - Store Discord records for later analysis
# Copyright (c) 2017 Ammon Smith
#
# discord-analytics is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

__all__ = [
    'id2timestamp',
    'null_logger',
    'plural',
]

def plural(x, suffix='s'):
    '''
    Assists in human-readable messages with plurals
    by returning the suffix if the value is not 1.
    '''

    if x == 1:
        return ''
    else:
        return suffix

def id2timestamp(id):
    '''
    Converts a Discord snowflake/ID into a UNIX timestamp.
    '''

    return (id // 4194304) + 1420070400000

class _NullLogger:
    def __init__(self):
        pass

    def debug(*args, **kwargs):
        pass

    def info(*args, **kwargs):
        pass

    def warning(*args, **kwargs):
        pass

    def error(*args, **kwargs):
        pass

null_logger = _NullLogger()
