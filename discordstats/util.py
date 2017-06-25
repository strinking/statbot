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
    'get_username',
    'get_emoji_name',
    'id2timestamp',
    'plural',
    'null_logger',
]

def get_username(member):
    '''
    Get's a user's nickname, if they have one,
    or just their username if they don't.
    '''

    if getattr(member, 'nick', None):
        return member.nick
    else:
        return member.name

def get_emoji_name(emoji):
    '''
    Get's an emoji's name, or the actual character
    itself if it's a unicode emoji.
    '''

    if type(emoji) == str:
        return emoji
    else:
        return emoji.name

def id2timestamp(id):
    '''
    Converts a Discord snowflake/ID into a UNIX timestamp.
    '''

    return (id // 4194304) + 1420070400000

def plural(x, suffix='s'):
    '''
    Assists in human-readable messages with plurals
    by returning the suffix if the value is not 1.
    '''

    if x == 1:
        return ''
    else:
        return suffix

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
