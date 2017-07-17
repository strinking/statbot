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
    def test_equals(self):
        self.assertEqual(Range(1, 4), Range(1, 4))
        self.assertEqual(PointRange(0), PointRange(0))
        self.assertEqual(MultiRange(), MultiRange())
        self.assertEqual(NullRange(), NullRange())

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
    def test_merge(self):
        self.assertEqual(MultiRange(Range(0, 1), Range(1, 2)), MultiRange(Range(0, 2)))
        self.assertEqual(MultiRange(Range(1, 2), Range(0, 1)), MultiRange(Range(0, 2)))
        self.assertEqual(MultiRange(Range(0, 1), Range(0, 1)), MultiRange(Range(0, 1)))
        self.assertEqual(MultiRange(Range(0, 3), Range(1, 4)), MultiRange(Range(0, 4)))

        self.assertEqual(MultiRange(Range(0, 1), Range(0, 2)), MultiRange(Range(0, 2)))
        self.assertEqual(MultiRange(Range(0, 2), Range(0, 1)), MultiRange(Range(0, 2)))
        self.assertEqual(MultiRange(Range(0, 1), Range(0, 2), Range(0, 3)), MultiRange(Range(0, 3)))
        self.assertEqual(MultiRange(Range(0, 2), Range(0, 3), Range(0, 1)), MultiRange(Range(0, 3)))
        self.assertEqual(MultiRange(Range(1, 5), Range(1, 5)), MultiRange(Range(1, 5)))

        self.assertEqual(MultiRange(Range(1, 3), Range(5, 8)), MultiRange(Range(1, 3), Range(5, 8)))
        self.assertEqual(MultiRange(Range(1, 3), Range(5, 8)), MultiRange(Range(5, 8), Range(1, 3)))

    def test_contains(self):
        m = MultiRange()
        self.assertNotIn(0, m)
        self.assertNotIn(2, m)

        m = MultiRange(Range(0, 3))
        self.assertNotIn(-1, m)
        self.assertIn(0, m)
        self.assertIn(2, m)
        self.assertNotIn(4, m)

        m = MultiRange(Range(0, 1), Range(3, 5))
        self.assertNotIn(-1, m)
        self.assertIn(0, m)
        self.assertIn(1, m)
        self.assertNotIn(2, m)
        self.assertIn(3, m)
        self.assertIn(4, m)
        self.assertIn(5, m)
        self.assertNotIn(6, m)

        m = MultiRange(Range(-1, 0), Range(3, 3), Range(6, 9))
        self.assertNotIn(-2, m)
        self.assertIn(-1, m)
        self.assertIn(0, m)
        self.assertNotIn(2, m)
        self.assertIn(3, m)
        self.assertNotIn(4, m)
        self.assertNotIn(5, m)
        self.assertIn(6, m)
        self.assertIn(8, m)
        self.assertIn(9, m)
        self.assertNotIn(10, m)

        m = MultiRange(Range(1, 2), Range(3, 4), Range(5, 6),
                Range(7, 8), Range(9, 10), Range(11, 12), Range(13, 14),
                Range(15, 16), Range(17, 18), Range(19, 20), Range(21, 22))
        self.assertNotIn(0, m)
        self.assertIn(1, m)
        self.assertNotIn(2.5, m)
        self.assertIn(3, m)
        self.assertNotIn(4.5, m)
        self.assertIn(5, m)
        self.assertNotIn(6.5, m)
        self.assertIn(7, m)
        self.assertNotIn(8.5, m)
        self.assertIn(9, m)
        self.assertNotIn(10.5, m)
        self.assertIn(11, m)
        self.assertNotIn(12.5, m)
        self.assertIn(13, m)
        self.assertNotIn(14.5, m)
        self.assertIn(15, m)
        self.assertNotIn(16.5, m)
        self.assertIn(17, m)
        self.assertNotIn(18.5, m)
        self.assertIn(19, m)
        self.assertNotIn(20.5, m)
        self.assertIn(21, m)
        self.assertNotIn(22.5, m)

    def test_minmax(self):
        m = MultiRange()
        self.assertEqual(None, m.min())
        self.assertEqual(None, m.max())

        m = MultiRange(Range(0, 1))
        self.assertEqual(0, m.min())
        self.assertEqual(1, m.max())

        m = MultiRange(Range(0, 1), Range(8, 9))
        self.assertEqual(0, m.min())
        self.assertEqual(9, m.max())

        m = MultiRange(Range(8, 9), Range(0, 1))
        self.assertEqual(0, m.min())
        self.assertEqual(9, m.max())

        m = MultiRange(Range(0, 1), Range(-5, -2), Range(4, 6))
        self.assertEqual(-5, m.min())
        self.assertEqual(6, m.max())

    def test_equals(self):
        self.assertEqual(MultiRange(), MultiRange())
        self.assertEqual(MultiRange(Range(0, 1)), MultiRange(Range(0, 1)))
        self.assertEqual(
                MultiRange(Range(-1, 0), Range(1, 2)),
                MultiRange(Range(1, 2), Range(-1, 0)))
        self.assertEqual(
                MultiRange(Range(0, 1), Range(2, 3), Range(9, 10)),
                MultiRange(Range(9, 10), Range(0, 1), Range(2, 3)))
        self.assertEqual(
                MultiRange(Range(0, 1), Range(1, 2), Range(2, 3)),
                MultiRange(Range(0, 3)))

    def test_bool(self):
        self.assertTrue(MultiRange(Range(0, 0)))
        self.assertTrue(MultiRange(Range(1, 3), Range(5, 7)))
        self.assertFalse(MultiRange())

    def test_union(self):
        m = MultiRange()
        self.assertEqual(m | Range(0, 1), MultiRange(Range(0, 1)))
        self.assertEqual(m | MultiRange(Range(0, 1)), MultiRange(Range(0, 1)))
        self.assertEqual(m, NULL_RANGE)
        self.assertEqual(m | m, m)

        m = MultiRange(Range(0, 1))
        self.assertEqual(m | Range(1, 2), MultiRange(Range(0, 2)))
        self.assertEqual(Range(1, 2) | m, MultiRange(Range(0, 2)))
        self.assertEqual(m | m, m)

        m = MultiRange(Range(1, 2), Range(5, 6))
        self.assertEqual(m | Range(2, 3), MultiRange(Range(1, 3), Range(5, 6)))
        self.assertEqual(m | Range(3, 4), MultiRange(Range(1, 2), Range(3, 4), Range(5, 6)))
        self.assertEqual(m | Range(0, 1), MultiRange(Range(0, 2), Range(5, 6)))
        self.assertEqual(m | Range(2, 5), MultiRange(Range(1, 6)))
        self.assertEqual(m | Range(2, 6), MultiRange(Range(1, 6)))
        self.assertEqual(m | Range(1, 5), MultiRange(Range(1, 6)))
        self.assertEqual(Range(2, 3) | m, MultiRange(Range(1, 3), Range(5, 6)))
        self.assertEqual(Range(3, 4) | m, MultiRange(Range(1, 2), Range(3, 4), Range(5, 6)))
        self.assertEqual(Range(0, 1) | m, MultiRange(Range(0, 2), Range(5, 6)))
        self.assertEqual(Range(2, 5) | m, MultiRange(Range(1, 6)))
        self.assertEqual(Range(2, 6) | m, MultiRange(Range(1, 6)))
        self.assertEqual(Range(1, 5) | m, MultiRange(Range(1, 6)))
        self.assertEqual(m | m, m)

        m = MultiRange(Range(0, 1), Range(4, 5), Range(8, 9))
        self.assertEqual(m | Range(0, 1), MultiRange(Range(0, 1), Range(4, 5), Range(8, 9)))
        self.assertEqual(m | Range(0, 4), MultiRange(Range(0, 5), Range(8, 9)))
        self.assertEqual(m | Range(5, 8), MultiRange(Range(0, 1), Range(4, 9)))
        self.assertEqual(m | Range(8, 9), MultiRange(Range(0, 1), Range(4, 5), Range(8, 9)))
        self.assertEqual(m | Range(7, 8), MultiRange(Range(0, 1), Range(4, 5), Range(7, 9)))
        self.assertEqual(Range(0, 1) | m, MultiRange(Range(0, 1), Range(4, 5), Range(8, 9)))
        self.assertEqual(Range(0, 4) | m, MultiRange(Range(0, 5), Range(8, 9)))
        self.assertEqual(Range(5, 8) | m, MultiRange(Range(0, 1), Range(4, 9)))
        self.assertEqual(Range(8, 9) | m, MultiRange(Range(0, 1), Range(4, 5), Range(8, 9)))
        self.assertEqual(Range(7, 8) | m, MultiRange(Range(0, 1), Range(4, 5), Range(7, 9)))
        self.assertEqual(m | m, m)

    def test_add(self):
        pass

