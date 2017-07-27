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

import unittest
from .message_history import MessageHistory
from .range import Range

class TestFindFirstHole(unittest.TestCase):
    def test_empty(self):
        mhist = MessageHistory()
        start = mhist.find_first_hole(20)
        self.assertEqual(start, 20)

        start = mhist.find_first_hole(100)
        self.assertEqual(start, 100)

    def test_continuous(self):
        mhist = MessageHistory(Range(5, 18))
        start = mhist.find_first_hole(50)
        self.assertEqual(start, 50)

        start = mhist.find_first_hole(20)
        self.assertEqual(start, 20)

    def test_hole(self):
        mhist = MessageHistory(Range(4, 12), Range(23, 31))
        start = mhist.find_first_hole(50)
        self.assertEqual(start, 50)

        start = mhist.find_first_hole(35)
        self.assertEqual(start, 35)

        start = mhist.find_first_hole(15)
        self.assertEqual(start, 15)

        mhist = MessageHistory(Range(5, 9), Range(13, 20), Range(31, 38), Range(50, 52))
        start = mhist.find_first_hole(10)
        self.assertEqual(start, 10)

        start = mhist.find_first_hole(25)
        self.assertEqual(start, 25)

        start = mhist.find_first_hole(70)
        self.assertEqual(start, 70)

    def test_aligned(self):
        mhist = MessageHistory(Range(18, 35))
        start = mhist.find_first_hole(35)
        self.assertEqual(start, 18)

        start = mhist.find_first_hole(18)
        self.assertEqual(start, 18)

    def test_aligned_hole(self):
        mhist = MessageHistory(Range(13, 22), Range(30, 35), Range(36, 49))
        start = mhist.find_first_hole(49)
        self.assertEqual(start, 36)

        start = mhist.find_first_hole(35)
        self.assertEqual(start, 30)

        start = mhist.find_first_hole(22)
        self.assertEqual(start, 13)
