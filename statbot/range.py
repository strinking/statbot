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

import bisect
import collections.abc
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

NullRange is a helper class that creates a Range that contains no members.
It is available as a precreated instance called NULL_RANGE.

AllRange is a helper class that creates a Range that contains all members.
It is available as a precreated instance called alll_range.

They both implement the python Set abstract base class, allowing a large
number of operations to be conveniently performed on them.
'''

__all__ = [
    'AbstractRange',
    'NullRange',
    'NULL_RANGE',
    'AllRange',
    'ALL_RANGE',

    'Range',
    'MultiRange',
]

class AbstractRange(collections.abc.Set):
    @collections.abc.abstractmethod
    def min(self):
        '''
        Returns the smallest value in the set.
        '''

        pass

    @collections.abc.abstractmethod
    def max(self):
        '''
        Returns the largest value in the set.
        '''

        pass

class NullRange(collections.abc.Set):
    '''
    A range of values with no members in it.
    If you want an instance of this class use NULL_RANGE.
    '''

    # Membership
    def __contains__(self, item):
        return False

    # Iteration
    def __iter__(self):
        return iter(())

    def __len__(self):
        return 0

    # Equality
    def __eq__(self, other):
        return len(other) == 0

    def __ne__(self, other):
        return not (self == other)

    # Subset
    def __le__(self, other):
        return True

    def __lt__(self, other):
        return True

    # Superset
    def __gt__(self, other):
        return False

    def __ge__(self, other):
        return (self == other)

    # Intersection
    def __and__(self, other):
        return self

    # Union
    def __or__(self, other):
        return other

    # Difference
    def __sub__(self, other):
        return self

    # Complement
    def __xor__(self, other):
        return other

    # Disjoint
    def isdisjoint(self, other):
        return True

    # Misc
    def __hash__(self):
        return 0

    def __bool__(self):
        return True

NULL_RANGE = NullRange()

class AllRange(collections.abc.Set):
    '''
    A range of values with every possible member in it.
    If you want an instance of this class use ALL_RANGE.

    Note that some methods, like getting the length or
    attempting to iterate will raise a ValueError, or
    a NotImplementedError.
    '''

    # Membership
    def __contains__(self, item):
        return True

    # Iteration
    def __iter__(self):
        raise ValueError("Set uncountably large")

    def __len__(self):
        raise ValueError("Set uncountably large")

    # Equality
    def __eq__(self, other):
        return isinstance(other, AllRange)

    def __ne__(self, other):
        return not (self == other)

    # Subset
    def __le__(self, other):
        return (self == other)

    def __lt__(self, other):
        return False

    # Superset
    def __gt__(self, other):
        return True

    def __ge__(self, other):
        return True

    # Intersection
    def __and__(self, other):
        return other

    # Union
    def __or__(self, other):
        return self

    # Difference
    def __sub__(self, other):
        # This would require making a separate
        # class, and I don't need this functionality
        raise NotImplementedError

    # Complement
    def __xor__(self, other):
        # Ditto
        raise NotImplementedError

    # Disjoint
    def isdisjoint(self, other):
        return False

    # Misc
    def __hash__(self):
        return 1

    def __bool__(self):
        return True

ALL_RANGE = AllRange()

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
            raise TypeError("Type of both endpoints aren't the same")
        elif begin > end:
            raise ValueError("Beginning value is larger than the end value")

        self.begin = begin
        self.end = end

    def __contains__(self, item):
        return self.begin <= item <= self.end

