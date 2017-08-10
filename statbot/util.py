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
    'get_null_id',
    'get_emoji_name',
    'get_emoji_id',
    'embeds_to_json',
    'null_logger',
]

def get_null_id(obj):
    '''
    If "obj" is None, return None.
    Otherwise get the "id" field and return it.
    '''

    if obj is None:
        return None
    else:
        return obj.id

def get_emoji_name(emoji):
    '''
    Gets an emoji's name, or the actual character
    itself if it's a unicode emoji.
    '''

    if isinstance(emoji, str):
        return emoji
    else:
        return emoji.name

def get_emoji_id(emoji):
    '''
    Gets a unique integer that represents a particular
    emoji. The id of a unicode emoji is its code point.
    '''

    if isinstance(emoji, str):
        return ord(emoji)
    else:
        return emoji.id

def embeds_to_json(embeds):
    return json.dumps([embed.to_dict() for embed in embeds])

class _NullLogger:
    __slots__ = ()

    def __init__(self):
        pass

    def debug(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

null_logger = _NullLogger()
