#
# message_utils.py
#
# discord-analytics - Store Discord records for later analysis
# Copyright (c) 2017 Ammon Smith
#
# discord-analytics is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

import re

URL_REGEX = re.compile(r'https?://[^ ]+')
MENTION_REGEX = re.compile(r'<@[0-9]+>')
CHANNEL_MENTION_REGEX = re.compile(r'<#[0-9]+>')
EMOJI_REGEX = re.compile(r'<:([A-Za-z]+):[0-9]+>')
CODEBLOCK_REGEX = re.compile(r'`(?:``)?[^`]+`(?:``)?')
SHRUG = r'¯\_(ツ)_/¯'
TABLE_FLIP = '(╯°□°）╯︵ ┻━┻'
TABLE_RESTORE = '┬─┬\ufeff ノ( ゜-゜ノ)'

__all__ = [
    'URL_REGEX',
    'MENTION_REGEX',
    'CHANNEL_MENTION_REGEX',
    'EMOJI_REGEX',
    'CODEBLOCK_REGEX',
    'SHRUG',
    'TABLE_FLIP',
    'TABLE_RESTORE',
    'get_message_stats',
]

def get_message_stats(message):
    '''
    Returns a dictionary with various stats about
    the passed discord message.
    '''

    text = message.contents
    return {
        'full': text,
        'emojis': EMOJI_REGEX.findall(text),
        'urls': URL_REGEX.findall(text),
        'mentions': MENTION_REGEX.findall(text),
        'channel_mentions': CHANNEL_MENTION_REGEX.findall(text),
        'bot': message.author.bot,
        'codeblock': bool(CODEBLOCK_REGEX.search(text)),
        'shrug': SHRUG in text,
        'table_flip': TABLE_FLIP in text,
        'table_restore': TABLE_RESTORE in text,
    }

