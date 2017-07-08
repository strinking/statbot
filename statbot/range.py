#
# range.py
#
# statbot - Store Discord records for later analysis
# Copyright (c) 2017 Ammon Smith
#
# statbot is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

import abc
import bisect
import heapq

'''
This module contains the definitions for two classes: Range and MultiRange.
Both represent a contiguous sequence of comparable items without the need
to store every single possible element in between.

Range is simply a pair of a start and stop value that designate the inclusive
set of values in between that are seen as being within the range.

MultiRange is a sorted group of Ranges, allowing for a large, non-contiguous
set of values. Some operations on a Range will return this value if the result
isn't contiguous.

They all implement the AbstractRange base class, guaranteeing a certain set of
operations that can be performed on them.
'''

__all__ = [
    'AbstractRange',
    'Range',
    'MultiRange',
]

def order(x, y):
    '''
    Returns these two objects such that the one with smaller value
    is first. If both are equivalent, the order in which they are
    returned is unspecified.
    '''

    if x < y:
        return (x, y)
    else:
        return (y, x)

class AbstractRange:
    @abc.abstractmethod
    def min(self):
        '''
        Returns the smallest value in the range.
        '''

        pass

    @abc.abstractmethod
    def max(self):
        '''
        Returns the largest value in the range.
        '''

        pass

    @abc.abstractmethod
    def clone(self):
        '''
        Returns a copy of the current object.
        '''

        pass

    @abc.abstractmethod
    def __or__(self, other):
        '''
        Returns the union between the two ranges.
        '''

        pass

    @abc.abstractmethod
    def __contains__(self, x):
        '''
        Determines if a value is within the range.
        '''

        pass

    @abc.abstractmethod
    def __eq__(self, other):
        pass

    @abc.abstractmethod
    def __hash__(self):
        pass

    @abc.abstractmethod
    def __bool__(self):
        pass

    def __lt__(self, other):
        if not isinstance(other, AbstractRange):
            raise TypeError(f"expected AbstractRange, not '{type(other)!r}'")

        return self.min() < other.min()

    def __le__(self, other):
        if not isinstance(other, AbstractRange):
            raise TypeError(f"expected AbstractRange, not '{type(other)!r}'")

        return self.min() <= other.min()

    def __gt__(self, other):
        if not isinstance(other, AbstractRange):
            raise TypeError(f"expected AbstractRange, not '{type(other)!r}'")

        return self.min() > other.min()

    def __ge__(self, other):
        if not isinstance(other, AbstractRange):
            raise TypeError(f"expected AbstractRange, not '{type(other)!r}'")

        return self.min() >= other.min()

class Range(AbstractRange):
    '''
    A contiguous range of values, from a given starting to a given ending point.
    '''

    __slots__ = (
        'begin',
        'end',
    )

    def __init__(self, begin, end):
        if type(begin) != type(end):
            raise TypeError("type of both endpoints aren't the same")
        elif begin > end:
            raise ValueError("beginning value is larger than the end value")

        self.begin = begin
        self.end = end

    def min(self):
        return self.begin

    def max(self):
        return self.end

    def clone(self):
        return Range(self.begin, self.end)

    def __contains__(self, item):
        return self.begin <= item <= self.end

    def __or__(self, other):
        if isinstance(other, Range):
            x, y = order(self, other)
            if x.end >= y.begin:
                return Range(x.begin, y.end)
            else:
                return MultiRange(x, y)
        elif isinstance(other, MultiRange):
            return other | self
        else:
            raise TypeError(f"cannot create union with unknown type: {type(other)!r}")

    def __eq__(self, other):
        if isinstance(other, Range):
            return (self.begin == other.begin) and (self.end == other.end)
        elif isinstance(other, MultiRange):
            return other == self
        else:
            return False

    def __hash__(self):
        return hash(self.begin) ^ hash(self.end)

    def __bool__(self):
        # Ranges always have at least one item in them
        return True

    def __repr__(self):
        return f"<Range object: [{self.begin!r}, {self.end!r}]>"

    def __str__(self):
        return f"[{self.begin}, {self.end}]"

class MultiRange(AbstractRange):
    '''
    A range of values, with support of discontinous jumps and other holes
    from the beginning to the end. This is implemented as a sorted list of
    Range objects.
    '''

    __slots__ = (
        'ranges',
    )

    def __init__(self, *ranges, _direct=None):
        for range in ranges:
            if not isinstance(range, Range):
                raise TypeError(f"MultiRange only supports Range objects, not {type(range)!r}.")

        if _direct is None:
            self.ranges = sorted(ranges)
        else:
            self.ranges = _direct

        self._merge()

    def _merge(self):
        '''
        Assumes "ranges" is sorted.
        This method walks through each range, merging it with its neighbors if
        they overlap.
        '''

        new_ranges = []
        last = None

        for current in self.ranges:
            if last is None:
                last = current
                continue

            if last.end >= current.begin:
                last = Range(last.begin, current.end)
            else:
                new_ranges.append(last)
                last = current

        if last:
            new_ranges.append(last)

        self.ranges = new_ranges

    def min(self):
        return self.ranges[0].min() if self.ranges else None

    def max(self):
        return self.ranges[-1].max() if self.ranges else None

    def clone(self):
        return MultiRange(*[range.clone() for range in self.ranges])

    def __contains__(self, item):
        begin = 0
        end = len(self.ranges) - 1

        while end > begin:
            mid = (end - begin) // 2
            range = self.ranges[mid]
            if item > range.max():
                begin = mid
            elif item < range.min():
                end = mid
            else:
                return True
        return False

    def __or__(self, other):
        if isinstance(other, Range):
            result = self.clone()
            result.add(other)
            return result
        elif isinstance(other, MultiRange):
            new_ranges = heapq.merge(self.ranges, other.ranges)
            return MultiRange(*(), _direct=list(new_ranges))
        else:
            raise TypeError(f"cannot create union with unknown type: {type(other)!r}")

    def add(self, range):
        if type(range) != Range:
            raise TypeError(f"expected Range, not '{type(range)!r}'")

        bisect.insort(self.ranges, range)
        self._merge()

    def __eq__(self, other):
        if isinstance(other, Range):
            return (len(self.ranges) == 1) and (self.ranges[0] == other)
        elif isinstance(other, MultiRange):
            return self.ranges == other.ranges
        else:
            return False

    def __hash__(self):
        return hash(self.ranges)

    def __bool__(self):
        return bool(self.ranges)

    def __repr__(self):
        leng = len(self.ranges)
        if leng > 4:
            return f"<MultiRange object: {leng} chunks>"
        else:
            return f"<MultiRange object: {self}>"

    def __str__(self):
            return ' u '.join(str(range) for range in self.ranges)
