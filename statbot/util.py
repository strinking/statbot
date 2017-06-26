#
# util.py
#
# statbot - Store Discord records for later analysis
# Copyright (c) 2017 Ammon Smith
#
# statbot is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

import json

__all__ = [
    'get_username',
    'get_emoji_name',
    'get_emoji_id',
    'plural',
    'embeds_to_json',
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
    Gets an emoji's name, or the actual character
    itself if it's a unicode emoji.
    '''

    if type(emoji) == str:
        return emoji
    else:
        return emoji.name

def get_emoji_id(emoji):
    '''
    Gets a unique integer that represents a particular
    emoji. The id of a unicode emoji is its code point.
    '''

    if type(emoji) == str:
        return ord(emoji)
    else:
        return emoji.id

def embeds_to_json(embeds):
    return json.dumps([embed.to_dict() for embed in embeds])

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
