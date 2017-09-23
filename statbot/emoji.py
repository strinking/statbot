#
# emoji.py
#
# statbot - Store Discord records for later analysis
# Copyright (c) 2017 Ammon Smith
#
# statbot is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

import unicodedata

__all__ = [
    'EmojiData',
]

class EmojiData:
    __slots__ = (
        'raw',
        'id',
        'unicode',
        'custom',
        'managed',
        'name',
        'category',
        'roles',
        'guild',
    )

    def __init__(self, emoji):
        self.raw = emoji

        if isinstance(emoji, str):
            self.id = 0
            self.unicode = emoji
            self.custom = False
            self.managed = False
            self.name = ';'.join(unicodedata.name(ch) for ch in emoji)
            self.category = ';'.join(unicodedata.category(ch) for ch in emoji)
            self.roles = []
            self.guild = None
        else:
            self.id = emoji.id
            self.unicode = ''
            self.custom = True
            self.managed = emoji.managed
            self.name = emoji.name
            self.category = f'[Custom: {emoji.guild.name}]'
            self.roles = emoji.roles
            self.guild = emoji.guild

    @property
    def mention(self):
        if self.id:
            return f'<:{self.name}:{self.id}>'
        else:
            return self.unicode

    @property
    def cache_id(self):
        return (self.id, self.unicode)

    def values(self):
        return {
            'emoji_id': self.id,
            'emoji_unicode': self.unicode,
            'is_custom': self.custom,
            'is_managed': self.managed,
            'is_deleted': False,
            'name': self.name,
            'category': self.category,
            'roles': [role.id for role in self.roles],
            'guild_id': getattr(self.guild, 'id', None),
        }

    def __str__(self):
        return str(self.id or self.unicode)

    def __repr__(self):
        return f'<EmojiData {self}>'
