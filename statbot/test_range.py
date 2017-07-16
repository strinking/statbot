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

from .range import *
import unittest

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

    def test_union(self):
        r = NullRange()
        self.assertEqual(NULL_RANGE | r, r)
        self.assertEqual(r | NULL_RANGE, r)

        r = PointRange(5)
        self.assertEqual(NULL_RANGE | r, r)
        self.assertEqual(r | NULL_RANGE, r)

        r = Range(0, 3)
        self.assertEqual(NULL_RANGE | r, r)
        self.assertEqual(r | NULL_RANGE, r)

        r = MultiRange(Range(1, 2), Range(5, 8))
        self.assertEqual(NULL_RANGE | r, r)
        self.assertEqual(r | NULL_RANGE, r)

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

    def test_union(self):
        self.assertEqual(PointRange(1) | PointRange(1), PointRange(1))
        self.assertEqual(PointRange(1) | PointRange(1), Range(1, 1))
        self.assertEqual(PointRange(1) | PointRange(2), MultiRange(Range(1, 1), Range(2, 2)))
        self.assertEqual(PointRange(1) | Range(2, 5), MultiRange(Range(1, 1), Range(2, 5)))
        self.assertEqual(PointRange(1) | Range(0, 2), Range(0, 2))
        self.assertEqual(Range(0, 2) | PointRange(1), Range(0, 2))

class TestRange(unittest.TestCase):
    def test_contains(self):
        r = Range(2, 5)
        self.assertNotIn(1, r)
        self.assertIn(2, r)
        self.assertIn(4, r)
        self.assertIn(5, r)
        self.assertNotIn(8, r)

        r = Range(-2, 0)
        self.assertNotIn(-3, r)
        self.assertIn(-2, r)
        self.assertIn(-1, r)
        self.assertIn(0, r)
        self.assertNotIn(1, r)

        r = Range(10, 10)
        self.assertNotIn(0, r)
        self.assertNotIn(9, r)
        self.assertIn(10, r)
        self.assertNotIn(11, r)

    def test_minmax(self):
        r = Range(4, 7)
        self.assertEqual(4, r.min())
        self.assertEqual(7, r.max())
        self.assertNotEqual(r.min(), r.max())

        r = Range(8, 8)
        self.assertEqual(8, r.min())
        self.assertEqual(8, r.max())
        self.assertEqual(r.min(), r.max())

    def test_equals(self):
        r = Range(3, 8)
        self.assertEqual(r, Range(3, 8))
        self.assertNotEqual(r, Range(2, 8))
        self.assertNotEqual(r, NULL_RANGE)

    def test_bool(self):
        self.assertTrue(Range(3, 5))
        self.assertTrue(Range(0, 0))

    def test_union(self):
        self.assertEqual(Range(0, 2) | Range(3, 4), MultiRange(Range(0, 2), Range(3, 4)))
        self.assertEqual(Range(3, 4) | Range(0, 2), MultiRange(Range(0, 2), Range(3, 4)))
        self.assertEqual(Range(0, 2) | Range(2, 4), Range(0, 4))
        self.assertEqual(Range(0, 3) | Range(1, 4), Range(0, 4))
        self.assertEqual(Range(1, 4) | Range(0, 3), Range(0, 4))
        self.assertEqual(Range(0, 1) | Range(0, 2), Range(0, 2))
        self.assertEqual(Range(0, 2) | Range(0, 1), Range(0, 2))
        self.assertEqual(Range(2, 8) | Range(4, 6), Range(2, 8))
        self.assertEqual(Range(4, 6) | Range(2, 8), Range(2, 8))

        self.assertEqual(Range(0, 2) | PointRange(3), MultiRange(Range(0, 2), Range(3, 3)))
        self.assertEqual(PointRange(3) | Range(0, 2), MultiRange(Range(0, 2), Range(3, 3)))
        self.assertEqual(Range(0, 3) | PointRange(2), Range(0, 3))
        self.assertEqual(PointRange(2) | Range(0, 3), Range(0, 3))
        self.assertEqual(Range(0, 3) | PointRange(3), Range(0, 3))
        self.assertEqual(PointRange(3) | Range(0, 3), Range(0, 3))
        self.assertEqual(Range(0, 1) | NULL_RANGE, Range(0, 1))
        self.assertEqual(NULL_RANGE | Range(0, 1), Range(0, 1))

class TestMultiRange(unittest.TestCase):
    def test_contains(self):
        pass

    def test_minmax(self):
        pass

    def test_equals(self):
        pass

    def test_bool(self):
        pass

    def test_union(self):
        pass

    def test_add(self):
        pass

