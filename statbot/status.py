#
# status.py
#
# statbot - Store Discord records for later analysis
# Copyright (c) 2017-2018 Ammon Smith
#
# statbot is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

from enum import Enum, unique

import discord

__all__ = [
    'UserStatus',
]

# Type "discord.Status" type conflicts with some Postgres thing,
# so we duplicate it here under a different name.

@unique
class UserStatus(Enum):
    ONLINE = 'ONLINE'
    OFFLINE = 'OFFLINE'
    IDLE = 'IDLE'
    DO_NOT_DISTURB = 'DO_NOT_DISTURB'

    @staticmethod
    def convert(status):
        return USER_STATUS_CONVERSION[status]

USER_STATUS_CONVERSION = {
    discord.Status.online: UserStatus.ONLINE,
    discord.Status.offline: UserStatus.OFFLINE,
    discord.Status.idle: UserStatus.IDLE,
    discord.Status.dnd: UserStatus.DO_NOT_DISTURB,
    discord.Status.do_not_disturb: UserStatus.DO_NOT_DISTURB,
    discord.Status.invisible: UserStatus.OFFLINE,
}
