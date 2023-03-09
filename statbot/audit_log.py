#
# audit_log.py
#
# statbot - Store Discord records for later analysis
# Copyright (c) 2017-2018 Ammon Smith
#
# statbot is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

import discord

from .util import int_hash

__all__ = [
    "AuditLogData",
]

NAME_ATTRS = (
    "name",
    "icon",
    "region",
    "afk_timeout",
    "widget_enabled",
    "verification_level",
    "explicit_content_filter",
    "default_message_notifications",
    "vanity_url_code",
    "position",
    "type",
    "topic",
    "bitrate",
    "nick",
    "deaf",
    "mute",
    "hoist",
    "mentionable",
    "code",
    "max_uses",
    "uses",
    "max_age",
    "temporary",
    "changed_id",
    "avatar",
)

ID_ATTRS = (
    "owner",
    "afk_channel",
    "system_channel",
    "widget_channel",
    "channel",
    "inviter",
)

VALUE_ATTRS = (
    "raw_role_permissions",
    "color",
    "raw_allow_permissions",
    "raw_deny_permissions",
)


class AuditLogData:
    __slots__ = (
        "entry",
        "guild",
    )

    def __init__(self, entry: discord.AuditLogEntry, guild: discord.Guild):
        self.entry = entry
        self.guild = guild

    def values(self):
        return {
            "audit_entry_id": self.entry.id,
            "guild_id": self.guild.id,
            "action": self.entry.action,
            "int_user_id": int_hash(self.entry.user.id),
            "reason": self.entry.reason,
            "category": self.entry.category,
            "before": self.diff_values(self.entry.before),
            "after": self.diff_values(self.entry.after),
        }

    @staticmethod
    def _get_overwrites(overwrites):
        if overwrites is None:
            return None

        targets = []
        allow_perms = []
        deny_perms = []

        for target, overwrite in overwrites:
            targets.append(target.id)
            allow, deny = overwrite.pair()
            allow_perms.append(allow.value)
            deny_perms.append(deny.value)

        return {
            "targets": targets,
            "allow": allow_perms,
            "deny": deny_perms,
        }

    def diff_values(self, diff):
        if self.entry.category is None:
            return None

        attributes = {}

        for attr in NAME_ATTRS:
            try:
                obj = getattr(diff, attr)
                attributes[attr] = obj
            except AttributeError:
                pass

        for attr in ID_ATTRS:
            try:
                obj = getattr(diff, attr)
                attributes[attr] = obj.id
            except AttributeError:
                pass

        for attr in VALUE_ATTRS:
            try:
                obj = getattr(diff, attr)
                attributes[attr] = obj.value
            except AttributeError:
                pass

        try:
            obj = getattr(diff, "mfa_level")
            attributes["mfa"] = bool(obj)
        except AttributeError:
            pass

        try:
            obj = getattr(diff, "roles")
            attributes["roles"] = list(map(lambda x: x.id, obj))
        except AttributeError:
            pass

        try:
            obj = self._get_overwrites(getattr(diff, "overwrites"))
            attributes["overwrites"] = obj
        except AttributeError:
            pass

        return attributes
