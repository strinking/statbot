#
# mention.py
#
# statbot - Store Discord records for later analysis
# Copyright (c) 2017-2018 Ammon Smith
#
# statbot is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

from enum import Enum

__all__ = [
    'MentionType',
]

class MentionType(Enum):
    USER = 0
    ROLE = 1
    CHANNEL = 2
