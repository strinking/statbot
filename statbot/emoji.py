#
# emoji.py
#
# statbot - Store Discord records for later analysis
# Copyright (c) 2017-2018 Ammon Smith
#
# statbot is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

import unicodedata

__all__ = [
    "EmojiData",
]


def get_unicode_data(emoji):
    try:
        name = [unicodedata.name(ch) for ch in emoji]
        category = [unicodedata.category(ch) for ch in emoji]
    except ValueError:
        # Couldn't find for codepoint
        name = [emoji]
        category = ["unicode_other"]

    return name, category


class EmojiData:
    __slots__ = (
        "raw",
        "id",
        "unicode",
        "custom",
        "managed",
        "name",
        "category",
        "roles",
        "guild",
    )

    def __init__(self, emoji):
        self.raw = emoji

        if isinstance(emoji, str):
            name, category = get_unicode_data(emoji)

            self.id = 0
            self.unicode = emoji
            self.custom = False
            self.managed = False
            self.name = name
            self.category = category
            self.roles = []
            self.guild = None
        else:
            self.id = emoji.id
            self.unicode = ""
            self.custom = True
            self.managed = getattr(emoji, "managed", None)
            self.name = [emoji.name]
            self.category = ["custom"]
            self.roles = getattr(emoji, "roles", None)
            self.guild = getattr(emoji, "guild", None)

    @property
    def mention(self):
        if self.id:
            return f"<:{self.name[0]}:{self.id}>"
        else:
            return self.unicode

    @property
    def cache_id(self):
        return (self.id, self.unicode)

    def values(self):
        return {
            "emoji_id": self.id,
            "emoji_unicode": self.unicode,
            "is_custom": self.custom,
            "is_managed": self.managed,
            "is_deleted": False,
            "name": self.name,
            "category": self.category,
            "roles": list(map(lambda r: r.id, self.roles or [])),
            "guild_id": getattr(self.guild, "id", None),
        }

    def __str__(self):
        return str(self.id or self.unicode)

    def __repr__(self):
        return f"<EmojiData {self}>"
