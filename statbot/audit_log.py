#
# audit_log.py
#
# statbot - Store Discord records for later analysis
# Copyright (c) 2017 Ammon Smith
#
# statbot is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

from enum import Enum

__all__ = [
    'AuditLogChangeState',
    'AuditLogData',
]

NAME_ATTRS = (
    'name',
    'icon',
    'region',
    'afk_timeout',
    'widget_enabled',
    'verification_level',
    'explicit_content_filter',
    'default_message_notifications',
    'vanity_url_code',
    'position',
    'type',
    'topic',
    'bitrate',
    'nick',
    'deaf',
    'mute',
    'hoist',
    'mentionable',
    'code',
    'max_uses',
    'uses',
    'max_age',
    'temporary',
    'changed_id',
    'avatar',
)

ID_ATTRS = (
    'owner',
    'afk_channel',
    'system_channel',
    'widget_channel',
    'channel',
    'inviter',
)

VALUE_ATTRS = (
    'raw_role_permissions',
    'color',
    'raw_allow_permissions',
    'raw_deny_permissions',
)

class AuditLogChangeState(Enum):
    BEFORE = 0
    AFTER = 1

class AuditLogData:
    __slots__ = (
        'entry',
        'guild',
    )

    def __init__(self, entry, guild):
        self.entry = entry
        self.guild = guild

    def values(self):
        return {
            'audit_entry_id': self.entry.id,
            'guild_id': self.guild.id,
            'action': self.entry.action,
            'user_id': self.entry.user.id,
            'reason': self.entry.reason,
            'category': self.entry.category,
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
            'targets': targets,
            'allow': allow_perms,
            'deny': deny_perms,
        }

    def diff_values(self, state):
        if self.entry.category is None:
            return None

        alcs = AuditLogChangeState(state)
        if alcs == AuditLogChangeState.BEFORE:
            diff = self.entry.before
        elif alcs == AuditLogChangeState.AFTER:
            diff = self.entry.after

        attributes = {}

        for attr in NAME_ATTRS:
            obj = getattr(diff, attr, None)
            if obj is not None:
                attributes[attr] = obj

        for attr in ID_ATTRS:
            obj = getattr(diff, attr, None)
            if obj is not None:
                attributes[attr] = obj.id

        for attr in VALUE_ATTRS:
            obj = getattr(diff, attr, None)
            if obj is not None:
                attributes[attr] = obj.value

        obj = getattr(diff, 'mfa_level', None)
        if obj is not None:
            attributes['mfa'] = bool(obj)

        obj = getattr(diff, 'roles', None)
        if obj is not None:
            attributes['roles'] = list(map(lambda x: x.id, obj))

        obj = self._get_overwrites(getattr(diff, 'overwrites', None))
        if obj is not None:
            attributes['overwrites'] = obj

        return {
            'audit_entry_id': self.entry.id,
            'guild_id': self.guild.id,
            'state': state,
            'attributes': attributes,
        }
