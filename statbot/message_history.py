#
# message_history.py
#
# statbot - Store Discord records for later analysis
# Copyright (c) 2017 Ammon Smith
#
# statbot is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

from .range import MultiRange, Range

__all__ = [
    'MessageHistory',
]

class MessageHistory(MultiRange):
    def __init__(self, *ranges):
        super().__init__(*ranges)

    def find_first_hole(self, start, max_size):
        current = start
        for range in reversed(self.ranges):
            if start > range.max():
                limit = current - range.max()
                return (current, min(limit, max_size))

            current = range.min()
        return (current, max_size)

    def __repr__(self):
        return super().__repr__(self).replace('MultiRange', 'MessageHistory')

