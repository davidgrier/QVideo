'''Unit tests for QFilterBank.'''
import unittest
import numpy as np
from qtpy import QtWidgets
from QVideo.lib.QFilterBank import QFilterBank
from QVideo.lib.QVideoFilter import QVideoFilter, VideoFilter


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_FRAME = np.zeros((4, 4), dtype=np.uint8)


def make_bank() -> QFilterBank:
    return QFilterBank(parent=None)


def make_filter() -> QVideoFilter:
    return QVideoFilter(None, 'Test', VideoFilter())


class TestQFilterBank(unittest.TestCase):

    def test_is_qgroupbox(self):
        bank = make_bank()
        self.assertIsInstance(bank, QtWidgets.QGroupBox)

    def test_title(self):
        bank = make_bank()
        self.assertEqual(bank.title(), 'Display Filters')

    def test_initially_empty(self):
        bank = make_bank()
        self.assertEqual(len(bank.filters), 0)

    def test_has_layout(self):
        bank = make_bank()
        self.assertIsInstance(bank._layout, QtWidgets.QVBoxLayout)

    def test_call_returns_frame_unchanged_when_empty(self):
        bank = make_bank()
        result = bank(_FRAME)
        np.testing.assert_array_equal(result, _FRAME)

    def test_register_rejects_non_qvideofilter(self):
        bank = make_bank()
        with self.assertRaises(TypeError):
            bank.register('not a filter')

    def test_register_adds_filter(self):
        bank = make_bank()
        f = make_filter()
        bank.register(f)
        self.assertIn(f, bank.filters)

    def test_register_adds_to_layout(self):
        bank = make_bank()
        f = make_filter()
        bank.register(f)
        self.assertEqual(bank._layout.count(), 1)

    def test_deregister_removes_filter(self):
        bank = make_bank()
        f = make_filter()
        bank.register(f)
        bank.deregister(f)
        self.assertNotIn(f, bank.filters)

    def test_deregister_removes_from_layout(self):
        bank = make_bank()
        f = make_filter()
        bank.register(f)
        bank.deregister(f)
        self.assertEqual(bank._layout.count(), 0)

    def test_deregister_detaches_widget(self):
        bank = make_bank()
        f = make_filter()
        bank.register(f)
        bank.deregister(f)
        self.assertIsNone(f.parent())

    def test_call_applies_filters_in_order(self):
        '''Filters are applied sequentially; each sees the previous output.'''
        bank = make_bank()
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
            bank.register(f)

        bank(_FRAME)
        self.assertEqual(log, ['a', 'b', 'c'])

    def test_register_by_name_known_filter(self):
        bank = make_bank()
        bank.registerByName('QBlurFilter')
        from QVideo.filters import QBlurFilter
        self.assertIsInstance(bank.filters[0], QBlurFilter)

    def test_register_by_name_unknown_raises(self):
        bank = make_bank()
        with self.assertRaises(ValueError):
            bank.registerByName('NonExistentFilter')

    def test_register_by_name_non_filter_raises(self):
        bank = make_bank()
        with self.assertRaises(ValueError):
            bank.registerByName('Median')

    def test_filters_property_returns_copy(self):
        bank = make_bank()
        f = make_filter()
        bank.register(f)
        snapshot = bank.filters
        snapshot.clear()
        self.assertIn(f, bank.filters)

    def test_iter_yields_filters_in_order(self):
        bank = make_bank()
        filters = [make_filter() for _ in range(3)]
        for f in filters:
            bank.register(f)
        self.assertEqual(list(bank), filters)

    def test_multiple_filters_registered(self):
        bank = make_bank()
        bank.registerByName('QBlurFilter')
        bank.registerByName('QRGBFilter')
        self.assertEqual(len(bank.filters), 2)


if __name__ == '__main__':
    unittest.main()
