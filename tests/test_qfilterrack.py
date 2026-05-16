'''Unit tests for QFilterRack.'''
import unittest
import numpy as np
from unittest.mock import patch
from qtpy import QtCore, QtWidgets
from QVideo.lib.QFilterRack import QFilterRack, _FilterSlot
from QVideo.lib.QVideoFilter import QVideoFilter, VideoFilter
from QVideo.filters import QSmoothingFilter, QEdgeFilter


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_FRAME = np.zeros((4, 4), dtype=np.uint8)


def make_rack(**kwargs) -> QFilterRack:
    return QFilterRack(parent=None, **kwargs)


def make_filter(title='Test') -> QVideoFilter:
    return QVideoFilter(None, title, VideoFilter())


class TestQFilterRackInit(unittest.TestCase):

    def test_is_qwidget(self):
        rack = make_rack()
        self.assertIsInstance(rack, QtWidgets.QWidget)

    def test_initially_empty(self):
        rack = make_rack()
        self.assertEqual(len(rack.filters), 0)

    def test_editable_true_by_default(self):
        rack = make_rack()
        self.assertTrue(rack.editable)

    def test_editable_false_hides_toolbar(self):
        rack = make_rack(editable=False)
        self.assertFalse(rack._toolbar.isVisible())

    def test_editable_setter_shows_toolbar(self):
        rack = make_rack(editable=False)
        rack.editable = True
        self.assertFalse(rack._toolbar.isHidden())

    def test_editable_setter_hides_toolbar(self):
        rack = make_rack(editable=True)
        rack.editable = False
        self.assertTrue(rack._toolbar.isHidden())


class TestQFilterRackAdd(unittest.TestCase):

    def test_add_rejects_non_qvideofilter(self):
        rack = make_rack()
        with self.assertRaises(TypeError):
            rack.add('not a filter')

    def test_add_appends_to_filters(self):
        rack = make_rack()
        f = make_filter()
        rack.add(f)
        self.assertIn(f, rack.filters)

    def test_add_two_filters(self):
        rack = make_rack()
        f1, f2 = make_filter('A'), make_filter('B')
        rack.add(f1)
        rack.add(f2)
        self.assertEqual(rack.filters, [f1, f2])

    def test_add_increments_slot_count(self):
        rack = make_rack()
        rack.add(make_filter())
        self.assertEqual(rack._slots.count(), 1)

    def test_add_creates_filter_slot(self):
        rack = make_rack()
        rack.add(make_filter())
        self.assertIsInstance(rack._slotAt(0), _FilterSlot)

    def test_add_slot_editable_matches_rack(self):
        rack = make_rack(editable=False)
        rack.add(make_filter())
        slot = rack._slotAt(0)
        self.assertFalse(slot._handle.isVisible())
        self.assertFalse(slot._closeButton.isVisible())


class TestQFilterRackAddByName(unittest.TestCase):

    def test_add_by_name_known_filter(self):
        rack = make_rack()
        with patch.object(QtCore.QThread, 'start'), \
             patch.object(QtCore.QObject, 'moveToThread'):
            rack.addByName('Smoothing')
        self.assertIsInstance(rack.filters[0], QSmoothingFilter)

    def test_add_by_name_unknown_raises(self):
        rack = make_rack()
        with self.assertRaises(ValueError):
            rack.addByName('No Such Filter')

    def test_add_by_name_non_filter_raises(self):
        rack = make_rack()
        with self.assertRaises(ValueError):
            rack.addByName('Median')


class TestQFilterRackAvailableFilters(unittest.TestCase):

    def test_returns_list(self):
        result = QFilterRack.availableFilters()
        self.assertIsInstance(result, list)

    def test_returns_sorted(self):
        result = QFilterRack.availableFilters()
        self.assertEqual(result, sorted(result))

    def test_contains_known_filters(self):
        result = QFilterRack.availableFilters()
        self.assertIn('Smoothing', result)
        self.assertIn('Canny Edge Detection', result)
        self.assertIn('Region of Interest', result)

    def test_excludes_non_widget_classes(self):
        result = QFilterRack.availableFilters()
        self.assertNotIn('Median', result)
        self.assertNotIn('SmoothingFilter', result)


class TestQFilterRackFiltersProperty(unittest.TestCase):

    def test_filters_returns_list(self):
        rack = make_rack()
        self.assertIsInstance(rack.filters, list)

    def test_filters_returns_copy(self):
        rack = make_rack()
        f = make_filter()
        rack.add(f)
        snapshot = rack.filters
        snapshot.clear()
        self.assertIn(f, rack.filters)

    def test_iter_yields_filters_in_order(self):
        rack = make_rack()
        f1, f2, f3 = make_filter('A'), make_filter('B'), make_filter('C')
        for f in (f1, f2, f3):
            rack.add(f)
        self.assertEqual(list(rack), [f1, f2, f3])


class TestQFilterRackCall(unittest.TestCase):

    def test_call_returns_frame_unchanged_when_empty(self):
        rack = make_rack()
        result = rack(_FRAME)
        np.testing.assert_array_equal(result, _FRAME)

    def test_call_applies_filters_in_order(self):
        rack = make_rack()
        log = []

        class LogFilter(VideoFilter):
            def __init__(self, tag):
                super().__init__()
                self.tag = tag

            def add(self, data):
                log.append(self.tag)
                self.data = data

        for tag in ('a', 'b', 'c'):
            f = QVideoFilter(None, tag, LogFilter(tag))
            f.setChecked(True)
            rack.add(f)

        rack(_FRAME)
        self.assertEqual(log, ['a', 'b', 'c'])

    def test_call_skips_unchecked_filter(self):
        rack = make_rack()
        log = []

        class LogFilter(VideoFilter):
            def __init__(self, tag):
                super().__init__()
                self.tag = tag

            def add(self, data):
                log.append(self.tag)
                self.data = data

        f = QVideoFilter(None, 'x', LogFilter('x'))
        f.setChecked(False)
        rack.add(f)
        rack(_FRAME)
        self.assertEqual(log, [])


class TestQFilterRackRemove(unittest.TestCase):

    def test_remove_slot_removes_filter(self):
        rack = make_rack()
        f = make_filter()
        rack.add(f)
        slot = rack._slotAt(0)
        rack._removeSlot(slot)
        self.assertNotIn(f, rack.filters)

    def test_remove_slot_decrements_count(self):
        rack = make_rack()
        rack.add(make_filter())
        slot = rack._slotAt(0)
        rack._removeSlot(slot)
        self.assertEqual(rack._slots.count(), 0)

    def test_remove_middle_slot(self):
        rack = make_rack()
        f1, f2, f3 = make_filter('A'), make_filter('B'), make_filter('C')
        for f in (f1, f2, f3):
            rack.add(f)
        slot_b = rack._slotAt(1)
        rack._removeSlot(slot_b)
        self.assertEqual(rack.filters, [f1, f3])


class TestQFilterRackMoveSlot(unittest.TestCase):

    def test_move_slot_no_target_does_not_raise(self):
        rack = make_rack()
        rack.add(make_filter())
        slot = rack._slotAt(0)
        from qtpy.QtCore import QPoint
        rack._moveSlot(slot, QPoint(9999, 9999))

    def test_move_slot_same_slot_does_not_reorder(self):
        rack = make_rack()
        f1, f2 = make_filter('A'), make_filter('B')
        rack.add(f1)
        rack.add(f2)
        slot = rack._slotAt(0)
        from qtpy.QtCore import QPoint
        rack._moveSlot(slot, QPoint(9999, 9999))
        self.assertEqual(rack.filters, [f1, f2])


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
