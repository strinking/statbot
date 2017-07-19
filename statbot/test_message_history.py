#
# test_message_history.py
#
# statbot - Store Discord records for later analysis
# Copyright (c) 2017 Ammon Smith
#
# statbot is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

from .message_history import MessageHistory
from .range import Range
import unittest

class TestFindFirstHole(unittest.TestCase):
    def test_empty(self):
        mhist = MessageHistory()
        start, count = mhist.find_first_hole(20, 10)
        self.assertEqual(start, 20)
        self.assertEqual(count, 10)

        start, count = mhist.find_first_hole(100, 10)
        self.assertEqual(start, 100)
        self.assertEqual(count, 10)

    def test_continuous(self):
        mhist = MessageHistory(Range(5, 18))
        start, count = mhist.find_first_hole(50, 10)
        self.assertEqual(start, 50)
        self.assertEqual(count, 10)

        start, count = mhist.find_first_hole(20, 10)
        self.assertEqual(start, 20)
        self.assertEqual(count, 2)

    def test_one_hole(self):
        mhist = MessageHistory(Range(4, 12), Range(23, 31))
        start, count = mhist.find_first_hole(50, 10)
        self.assertEqual(start, 50)
        self.assertEqual(count, 10)

        start, count = mhist.find_first_hole(35, 10)
        self.assertEqual(start, 35)
        self.assertEqual(count, 4)

    def test_many_holes(self):
        mhist = MessageHistory(Range(5, 9), Range(13, 20), Range(31, 38), Range(50, 52))
        start, count = mhist.find_first_hole(100, 10)
        self.assertEqual(start, 100)
        self.assertEqual(count, 10)

        start, count = mhist.find_first_hole(70, 10)
        self.assertEqual(start, 70)
        self.assertEqual(count, 10)

    def test_aligned(self):
        mhist = MessageHistory(Range(18, 35))
        start, count = mhist.find_first_hole(35, 10)
        self.assertEqual(start, 18)
        self.assertEqual(count, 10)

        start, count = mhist.find_first_hole(18, 10)
        self.assertEqual(start, 18)
        self.assertEqual(count, 10)

    def test_aligned_hole(self):
        mhist = MessageHistory(Range(13, 22), Range(30, 35))
        start, count = mhist.find_first_hole(35, 10)
        self.assertEqual(start, 30)
        self.assertEqual(count, 8)

        start, count = mhist.find_first_hole(22, 10)
        self.assertEqual(start, 13)
        self.assertEqual(count, 10)

