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
    'AuditLogPermissionType',
    'AuditLogData',
]

class AuditLogChangeState(Enum):
    BEFORE = 0
    AFTER = 1

class AuditLogPermissionType(Enum):
    TEXT_CHANNEL = 0
    VOICE_CHANNEL = 1
    ROLE = 2
    MEMBER = 3

    @classmethod
    def from_raw(cls, obj):
        return {
            0: cls.TEXT_CHANNEL,
            1: cls.VOICE_CHANNEL,
            'role': cls.ROLE,
            'member': cls.MEMBER,
        }[obj]

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
            'action': self.entry.action,
            'user_id': self.entry.user.id,
            'reason': self.entry.reason,
            'category': self.entry.category,
        }

    @staticmethod
    def _get_overwrites(overwrites):
        if overwrites is None:
            return None, None, None

        targets = []
        allow_perms = []
        deny_perms = []

        for target, overwrite in overwrites:
            targets.append(target.id)
            allow, deny = overwrite.pair()
            allow_perms.append(allow)
            deny_perms.append(deny)

        return targets, allow_perms, deny_perms

    def diff_values(self, state):
        if self.entry.category is None:
            return None

        if state == AuditLogChangeState.BEFORE:
            diff = self.entry.before
        else:
            diff = self.entry.after

        targets, allow_perms, deny_perms = self._get_overwrites(getattr(diff, 'overwrites', None))

        def get(attr, func=None):
            obj = getattr(diff, attr, None)
            if func and obj is not None:
                return func(obj)
            else:
                return obj

        def get_id(attr):
            return get(attr, lambda x: x.id)

        def get_value(attr):
            return get(attr, lambda x: x.value)

        return {
            'state': state,
            'name': get('name'),
            'icon': get('icon'),
            'owner': get_id('owner'),
            'region': get('region'),
            'afk_channel': get_id('afk_channel'),
            'system_channel': get_id('system_channel'),
            'afk_timeout': get('afk_timeout'),
            'mfa': get('mfa_level', bool),
            'widget_enabled': get('widget_enabled'),
            'widget_channel': get_id('widget_channel'),
            'verification_level': get('verification_level'),
            'explicit_content_filter': get('explicit_content_filter'),
            'default_message_notifications': get('default_message_notifications'),
            'vanity_url_code': get('vanity_url_code'),
            'position': get('position'),
            'type': get('type', AuditLogPermissionType.from_raw),
            'topic': get('topic'),
            'bitrate': get('bitrate'),
            'overwrite_targets': targets,
            'overwrite_allow_permissions': allow_perms,
            'overwrite_deny_permissions': deny_perms,
            'roles': get('roles', lambda roles: [role.id for role in roles]),
            'nickname': get('nick'),
            'deaf': get('deaf'),
            'mute': get('mute'),
            'raw_role_permissions': get_value('permissions'),
            'color': get_value('color'),
            'hoist': get('hoist'),
            'mentionable': get('mentionable'),
            'code': get('code'),
            'channel': get_id('channel'),
            'inviter': get_id('inviter'),
            'max_uses': get('max_uses'),
            'uses': get('uses'),
            'max_age': get('max_age'),
            'temporary': get('temporary'),
            'raw_allow_permissions': get_value('allow'),
            'raw_deny_permissions': get_value('deny'),
            'changed_id': get('id'),
            'avatar': get('avatar'),
        }
