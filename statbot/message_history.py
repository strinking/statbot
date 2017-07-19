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
    __slots__ = (
        'finished',
    )

    def __init__(self, *ranges):
        super().__init__(*ranges)
        self.finished = False

    def find_first_hole(self, start, max_size):
        if self.finished:
            return (start, 0)

        current = start
        for range in reversed(self.ranges):
            if start > range.max():
                limit = current - range.max()
                return (current, min(limit, max_size))

            current = range.min()
        return (current, max_size)

    def __repr__(self):
        if self.finished:
            state = ' (finished)'
        else:
            state = ''

        leng = len(self.ranges)
        if leng > 4:
            return f"<MessageHistory object: {leng} chunks{state}>"
        elif leng == 0:
            return f"<MessageHistory object: []{state}>"
        else:
            return f"<MessageHistory object: {self}{state}>"

