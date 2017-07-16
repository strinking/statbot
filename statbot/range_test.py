#
# range_test.py
#
# statbot - Store Discord records for later analysis
# Copyright (c) 2017 Ammon Smith
#
# statbot is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

from range import *
import unittest

class TestNullRange(unittest.TestCase):
    def test_contains(self):
        self.assertNotIn(0, NULL_RANGE)
        self.assertNotIn(None, NULL_RANGE)
        self.assertNotIn('a', NULL_RANGE)

    def test_minmax(self):
        self.assertIs(NULL_RANGE.min(), None)
        self.assertIs(NULL_RANGE.max(), None)

    def test_equals(self):
        self.assertEqual(NULL_RANGE, NullRange())
        self.assertNotEqual(NULL_RANGE, PointRange(0))
        self.assertNotEqual(NULL_RANGE, None)

    def test_bool(self):
        self.assertFalse(NULL_RANGE)
        self.assertFalse(NullRange())

class TestPointRange(unittest.TestCase):
    def test_contains(self):
        r = PointRange(5)

        self.assertIn(5, r)
        self.assertNotIn(2, r)

    def test_minmax(self):
        r = PointRange(-2)

        self.assertEqual(r.min(), r.max())
        self.assertEqual(-2, r.min())

    def test_equals(self):
        r = PointRange('e')

        self.assertEqual(PointRange('e'), r)
        self.assertNotEqual(PointRange('a'), r)
        self.assertNotEqual(NULL_RANGE, r)

    def test_bool(self):
        self.assertTrue(PointRange(0))
        self.assertTrue(PointRange('beta'))

class TestMisc(unittest.TestCase):
    def test_types(self):
        r = Range(0, 3)
        m = MultiRange()
        p = PointRange(-3)
        n = NullRange()

        self.assertIsInstance(r, AbstractRange)
        self.assertIsInstance(m, AbstractRange)
        self.assertIsInstance(p, AbstractRange)
        self.assertIsInstance(n, AbstractRange)

