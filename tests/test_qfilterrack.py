'''Unit tests for QFilterRack: a rack of filter widgets with a pipeline.'''
import sys
import tempfile
import time
import unittest
from pathlib import Path
import numpy as np
from unittest.mock import MagicMock, patch
from qtpy import QtCore, QtGui, QtTest, QtWidgets
from QVideo.lib import QFilterPipeline
from QVideo.lib.QFilterRack import (QFilterRack, _FilterSlot, _FilterPicker,
                                    _DragHandle)
from QVideo.tests.signals import record
from QVideo.lib.QVideoFilter import QVideoFilter, VideoFilter
from QVideo.lib.videotypes import FrameInfo
from QVideo.filters import QSmoothingFilter, QEdgeFilter


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_FRAME = np.zeros((4, 4), dtype=np.uint8)

_module = sys.modules['QVideo.lib.QFilterRack']  # not the class


_racks = []


def make_rack(**kwargs) -> QFilterRack:
    '''A rack, whose pipeline is stopped when the tests of the module end.'''
    rack = QFilterRack(parent=None, **kwargs)
    _racks.append(rack)
    return rack


def tearDownModule():
    for rack in _racks:
        rack.pipeline.stop()
    _racks.clear()


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

    def test_returns_dict(self):
        result = QFilterRack.availableFilters()
        self.assertIsInstance(result, dict)

    def test_names_are_sorted(self):
        result = QFilterRack.availableFilters()
        self.assertEqual(list(result), sorted(result))

    def test_contains_known_filters(self):
        result = QFilterRack.availableFilters()
        self.assertIn('Smoothing', result)
        self.assertIn('Canny', result)
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


class TestQFilterRackNoResult(unittest.TestCase):
    '''A filter with no result yet ends the frame, as in the pipeline.'''

    def setUp(self):
        self.rack = make_rack()
        self.seen = []
        seen = self.seen

        class Nothing(VideoFilter):
            def get(self):
                return None

        class Recorder(VideoFilter):
            def add(self, data):
                seen.append(data)
                self.data = data

        for video_filter in (Nothing(), Recorder()):
            widget = QVideoFilter(None, 'x', video_filter)
            widget.setChecked(True)
            self.rack.add(widget)

    def test_the_next_filter_is_not_given_nothing(self):
        self.assertIsNone(self.rack(_FRAME))
        self.assertEqual(self.seen, [])


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


class TestQFilterRackActiveFilters(unittest.TestCase):

    def test_empty_rack_has_no_active_filters(self):
        self.assertEqual(make_rack().activeFilters(), [])

    def test_returns_the_video_filters_of_checked_widgets(self):
        rack = make_rack()
        a, b = make_filter('A'), make_filter('B')
        for w in (a, b):
            w.setChecked(True)
            rack.add(w)
        self.assertEqual(rack.activeFilters(), [a.videoFilter, b.videoFilter])

    def test_unchecked_widgets_are_left_out(self):
        rack = make_rack()
        a, b = make_filter('A'), make_filter('B')
        b.setChecked(True)
        rack.add(a)
        rack.add(b)
        self.assertEqual(rack.activeFilters(), [b.videoFilter])

    def test_follows_the_rack_order(self):
        rack = make_rack()
        a, b = make_filter('A'), make_filter('B')
        for w in (a, b):
            w.setChecked(True)
            rack.add(w)
        slot0, slot1 = rack._slotAt(0), rack._slotAt(1)
        slot0.geometry = lambda: QtCore.QRect(0, 0, 10, 10)
        slot1.geometry = lambda: QtCore.QRect(0, 20, 10, 10)
        with patch.object(rack, 'mapFromGlobal',
                          return_value=QtCore.QPoint(1, 21)):
            rack._moveSlot(slot0, QtCore.QPoint(0, 0))
        self.assertEqual(rack.activeFilters(), [b.videoFilter, a.videoFilter])


class TestSlotUnder(unittest.TestCase):

    def test_finds_the_slot_at_a_point_and_none_elsewhere(self):
        rack = make_rack()
        a, b = make_filter('A'), make_filter('B')
        for w in (a, b):
            rack.add(w)
        slot0, slot1 = rack._slotAt(0), rack._slotAt(1)
        slot0.geometry = lambda: QtCore.QRect(0, 0, 10, 10)
        slot1.geometry = lambda: QtCore.QRect(0, 20, 10, 10)
        for point, expected in ((QtCore.QPoint(1, 1), slot0),
                                (QtCore.QPoint(1, 21), slot1),
                                (QtCore.QPoint(50, 50), None)):
            with patch.object(rack, 'mapFromGlobal', return_value=point):
                self.assertIs(rack._slotUnder(QtCore.QPoint(0, 0)), expected)


class TestDragHandle(unittest.TestCase):

    def event(self, kind, button, buttons):
        return QtGui.QMouseEvent(
            kind, QtCore.QPointF(2, 2), button, buttons,
            QtCore.Qt.KeyboardModifier.NoModifier)

    def send(self, handle, kind, button, buttons=None):
        QtWidgets.QApplication.sendEvent(
            handle, self.event(kind, button, buttons or button))

    def setUp(self):
        self.handle = _DragHandle()
        self.dragged = record(self.handle.dragging)
        self.dropped = record(self.handle.dropped)
        cursor = patch.object(QtGui.QCursor, 'pos',
                              return_value=QtCore.QPoint(7, 9))
        cursor.start()
        self.addCleanup(cursor.stop)

    def test_pressing_closes_the_hand(self):
        Left = QtCore.Qt.MouseButton.LeftButton
        self.send(self.handle, QtCore.QEvent.Type.MouseButtonPress, Left)
        self.assertEqual(self.handle.cursor().shape(),
                         QtCore.Qt.CursorShape.ClosedHandCursor)

    def test_dragging_reports_where_the_cursor_is(self):
        Left = QtCore.Qt.MouseButton.LeftButton
        self.send(self.handle, QtCore.QEvent.Type.MouseMove,
                  QtCore.Qt.MouseButton.NoButton, Left)
        self.assertEqual(self.dragged, [(QtCore.QPoint(7, 9),)])

    def test_moving_without_a_button_reports_nothing(self):
        No = QtCore.Qt.MouseButton.NoButton
        self.send(self.handle, QtCore.QEvent.Type.MouseMove, No, No)
        self.assertEqual(self.dragged, [])

    def test_releasing_drops_and_opens_the_hand(self):
        Left = QtCore.Qt.MouseButton.LeftButton
        self.send(self.handle, QtCore.QEvent.Type.MouseButtonPress, Left)
        self.send(self.handle, QtCore.QEvent.Type.MouseButtonRelease, Left,
                  QtCore.Qt.MouseButton.NoButton)
        self.assertEqual(self.dropped, [(QtCore.QPoint(7, 9),)])
        self.assertEqual(self.handle.cursor().shape(),
                         QtCore.Qt.CursorShape.OpenHandCursor)

    def test_releasing_another_button_does_not_drop(self):
        Right = QtCore.Qt.MouseButton.RightButton
        self.send(self.handle, QtCore.QEvent.Type.MouseButtonRelease, Right,
                  QtCore.Qt.MouseButton.NoButton)
        self.assertEqual(self.dropped, [])


class TestQFilterRackEditable(unittest.TestCase):

    def test_locking_the_rack_hides_the_controls_of_each_filter(self):
        rack = make_rack()
        rack.add(make_filter('A'))
        rack.add(make_filter('B'))
        rack.editable = False
        for slot in rack._iterSlots():
            self.assertTrue(slot._handle.isHidden())
            self.assertTrue(slot._closeButton.isHidden())
        rack.editable = True
        for slot in rack._iterSlots():
            self.assertFalse(slot._handle.isHidden())


class TestQFilterRackHover(unittest.TestCase):

    def test_the_slot_under_a_dragged_one_is_highlighted(self):
        rack = make_rack()
        rack.add(make_filter('A'))
        rack.add(make_filter('B'))
        first, second = list(rack._iterSlots())
        with patch.object(rack, '_slotUnder', return_value=second):
            rack._hoverSlot(first, QtCore.QPoint(0, 0))
        self.assertTrue(first._dropIndicator.isHidden())
        self.assertFalse(second._dropIndicator.isHidden())

    def test_the_dragged_slot_is_never_highlighted(self):
        rack = make_rack()
        rack.add(make_filter('A'))
        first = next(iter(rack._iterSlots()))
        with patch.object(rack, '_slotUnder', return_value=first):
            rack._hoverSlot(first, QtCore.QPoint(0, 0))
        self.assertTrue(first._dropIndicator.isHidden())


class TestQFilterRackDialogs(unittest.TestCase):

    def test_export_writes_the_pipeline_to_the_chosen_file(self):
        rack = make_rack()
        rack.add(QEdgeFilter())
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'filter.py')
            with patch.object(QtWidgets.QFileDialog, 'getSaveFileName',
                              return_value=(path, '')):
                rack._exportDialog()
            self.assertEqual(Path(path).read_text(encoding='utf-8'),
                             rack.exportPipeline())

    def test_cancelling_the_export_writes_nothing(self):
        rack = make_rack()
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(QtWidgets.QFileDialog, 'getSaveFileName',
                              return_value=('', '')):
                rack._exportDialog()
            self.assertEqual(list(Path(folder).iterdir()), [])

    def picker(self, result, name='Edge'):
        picker = MagicMock()
        picker.exec.return_value = result
        picker.selected.return_value = name
        return picker

    def test_the_chosen_filter_is_added(self):
        rack = make_rack()
        Accepted = QtWidgets.QDialog.DialogCode.Accepted
        with patch.object(rack, 'availableFilters', return_value={'Edge': object}), \
                patch.object(_module, '_FilterPicker',
                             return_value=self.picker(Accepted)), \
                patch.object(rack, 'addByName') as add:
            rack._addFilterDialog()
        add.assert_called_once_with('Edge')

    def test_a_cancelled_dialog_adds_nothing(self):
        rack = make_rack()
        Rejected = QtWidgets.QDialog.DialogCode.Rejected
        with patch.object(rack, 'availableFilters', return_value={'Edge': object}), \
                patch.object(_module, '_FilterPicker',
                             return_value=self.picker(Rejected)), \
                patch.object(rack, 'addByName') as add:
            rack._addFilterDialog()
        add.assert_not_called()

    def test_nothing_is_added_when_nothing_is_selected(self):
        rack = make_rack()
        Accepted = QtWidgets.QDialog.DialogCode.Accepted
        with patch.object(rack, 'availableFilters', return_value={'Edge': object}), \
                patch.object(_module, '_FilterPicker',
                             return_value=self.picker(Accepted, name=None)), \
                patch.object(rack, 'addByName') as add:
            rack._addFilterDialog()
        add.assert_not_called()

    def test_there_is_no_dialog_without_filters_to_offer(self):
        rack = make_rack()
        with patch.object(rack, 'availableFilters', return_value={}), \
                patch.object(_module, '_FilterPicker') as picker:
            rack._addFilterDialog()
        picker.assert_not_called()


class TestQFilterRackFiltersChanged(unittest.TestCase):
    '''filtersChanged tells a QFilterPipeline when to refresh its list.'''

    def setUp(self):
        self.rack = make_rack()
        self.count = []
        self.rack.filtersChanged.connect(lambda: self.count.append(1))

    def test_emitted_when_a_filter_is_added(self):
        self.rack.add(make_filter())
        self.assertEqual(len(self.count), 1)

    def test_emitted_when_a_filter_is_toggled(self):
        widget = make_filter()
        self.rack.add(widget)
        self.count.clear()
        widget.setChecked(True)
        widget.setChecked(False)
        self.assertEqual(len(self.count), 2)

    def test_emitted_when_a_filter_is_removed(self):
        self.rack.add(make_filter())
        self.count.clear()
        self.rack._removeSlot(self.rack._slotAt(0))
        self.assertEqual(len(self.count), 1)

    def test_emitted_when_a_filter_is_moved(self):
        for title in 'AB':
            self.rack.add(make_filter(title))
        self.count.clear()
        slot0, slot1 = self.rack._slotAt(0), self.rack._slotAt(1)
        slot0.geometry = lambda: QtCore.QRect(0, 0, 10, 10)
        slot1.geometry = lambda: QtCore.QRect(0, 20, 10, 10)
        with patch.object(self.rack, 'mapFromGlobal',
                          return_value=QtCore.QPoint(1, 21)):
            self.rack._moveSlot(slot0, QtCore.QPoint(0, 0))
        self.assertEqual(len(self.count), 1)

    def test_not_emitted_when_a_move_changes_nothing(self):
        self.rack.add(make_filter())
        self.count.clear()
        self.rack._moveSlot(self.rack._slotAt(0), QtCore.QPoint(9999, 9999))
        self.assertEqual(self.count, [])


class TestQFilterRackSwitchOff(unittest.TestCase):

    def test_unchecks_the_widget_holding_the_filter(self):
        rack = make_rack()
        a, b = make_filter('A'), make_filter('B')
        for w in (a, b):
            w.setChecked(True)
            rack.add(w)
        rack.switchOff(b.videoFilter, ValueError('bad'))
        self.assertTrue(a.isChecked())
        self.assertFalse(b.isChecked())
        self.assertIn('bad', b.toolTip())

    def test_unknown_filter_is_ignored(self):
        rack = make_rack()
        rack.add(make_filter())
        rack.switchOff(VideoFilter(), ValueError('bad'))


class TestQFilterRackFilterClasses(unittest.TestCase):

    def test_available_filters_map_name_to_class(self):
        reg = QFilterRack.availableFilters()
        self.assertIs(reg.get('Smoothing'), QSmoothingFilter)

    def test_available_filters_exclude_empty_display_name(self):
        reg = QFilterRack.availableFilters()
        for name in reg:
            self.assertTrue(name)

    def test_display_category_on_known_filters(self):
        from QVideo.filters import QThresholdFilter, QROIFilter
        self.assertEqual(QThresholdFilter.display_category, 'Segmentation')
        self.assertEqual(QROIFilter.display_category, 'Preprocessing')
        self.assertEqual(QEdgeFilter.display_category, 'Edge Detection')
        self.assertEqual(QSmoothingFilter.display_category, 'Preprocessing')


class TestFilterPicker(unittest.TestCase):

    def _make_registry(self) -> dict:
        return QFilterRack.availableFilters()

    def test_picker_creates_tree(self):
        picker = _FilterPicker(self._make_registry())
        self.assertIsInstance(picker._tree, QtWidgets.QTreeWidget)

    def test_picker_selected_none_when_nothing_selected(self):
        picker = _FilterPicker(self._make_registry())
        self.assertIsNone(picker.selected())

    def test_picker_selected_none_for_category_item(self):
        picker = _FilterPicker(self._make_registry())
        # Select the first top-level (category) item
        cat_item = picker._tree.topLevelItem(0)
        picker._tree.setCurrentItem(cat_item)
        self.assertIsNone(picker.selected())

    def test_picker_selected_returns_filter_name(self):
        picker = _FilterPicker(self._make_registry())
        # Find a leaf item and select it
        cat_item = picker._tree.topLevelItem(0)
        leaf_item = cat_item.child(0)
        picker._tree.setCurrentItem(leaf_item)
        name = picker.selected()
        self.assertIn(name, QFilterRack.availableFilters())

    def test_picker_categories_are_not_selectable(self):
        picker = _FilterPicker(self._make_registry())
        cat_item = picker._tree.topLevelItem(0)
        selectable = bool(
            cat_item.flags() & QtCore.Qt.ItemFlag.ItemIsSelectable)
        self.assertFalse(selectable)

    def test_picker_empty_category_falls_back_to_other(self):
        class _Uncategorized(QVideoFilter):
            display_name = 'Uncategorized'
            display_category = ''

            def __init__(self, parent=None):
                super().__init__(parent, 'Uncategorized', VideoFilter())

        registry = {'Uncategorized': _Uncategorized}
        picker = _FilterPicker(registry)
        cat_item = picker._tree.topLevelItem(0)
        self.assertEqual(cat_item.text(0), 'Other')


class _Source(QtCore.QObject):
    '''Stands in for a QVideoSource.'''
    newFrame = QtCore.Signal(np.ndarray, object)
    shapeChanged = QtCore.Signal(QtCore.QSize)
    fps = 30.
    shape = QtCore.QSize(4, 4)

    def send(self, index: int) -> None:
        frame = np.full((4, 4), index, dtype=np.uint8)
        self.newFrame.emit(frame, FrameInfo(index, float(index)))


class _Add(VideoFilter):
    def __init__(self, n):
        super().__init__()
        self.n = n

    def __call__(self, image):
        return image + self.n


def wait_until(condition, timeout=3.):
    deadline = time.monotonic() + timeout
    while not condition() and time.monotonic() < deadline:
        QtTest.QTest.qWait(5)
    return condition()


class RackTestCase(unittest.TestCase):

    def make(self, **kwargs) -> QFilterRack:
        rack = QFilterRack(**kwargs)
        self.addCleanup(rack.pipeline.stop)
        return rack


class TestStructure(RackTestCase):

    def test_owns_a_running_pipeline(self):
        rack = self.make()
        self.assertIsInstance(rack.pipeline, QFilterPipeline)
        self.assertTrue(rack.pipeline.isRunning())

    def test_the_pipeline_follows_the_rack(self):
        rack = self.make()
        self.assertIs(rack.pipeline.rack, rack)

    def test_without_a_source_the_pipeline_is_idle(self):
        self.assertIsNone(self.make().pipeline.upstream)

    def test_parent_and_editable_keep_their_positions(self):
        parent = QtWidgets.QWidget()
        rack = self.make(parent=parent, editable=False)
        self.assertIs(rack.parent(), parent)
        self.assertFalse(rack.editable)

    def test_depth_reaches_the_pipeline(self):
        rack = self.make(depth=8)
        self.assertEqual(rack.pipeline._stage._queue.maxlen, 8)


class TestSource(RackTestCase):

    def test_the_constructor_gives_the_pipeline_its_source(self):
        source = _Source()
        self.assertIs(self.make(source=source).pipeline.upstream, source)

    def test_source_reads_and_sets_the_pipeline_source(self):
        rack = self.make()
        source = _Source()
        rack.source = source
        self.assertIs(rack.pipeline.upstream, source)
        self.assertIs(rack.source, source)


class TestFiltering(RackTestCase):

    def test_frames_pass_through_the_switched_on_filters(self):
        source = _Source()
        rack = self.make(source=source)
        widget = QVideoFilter(None, '+5', _Add(5))
        widget.setChecked(True)
        rack.add(widget)
        out = []
        rack.pipeline.newFrame.connect(
            lambda frame, info: out.append(int(frame[0, 0])))
        source.send(1)
        self.assertTrue(wait_until(lambda: out))
        self.assertEqual(out, [6])

    def test_a_pipeline_of_your_own_still_works(self):
        source = _Source()
        rack = self.make()
        own = QFilterPipeline(source, rack=rack)
        self.addCleanup(own.stop)
        widget = QVideoFilter(None, '+5', _Add(5))
        widget.setChecked(True)
        rack.add(widget)
        out = []
        own.newFrame.connect(
            lambda frame, info: out.append(int(frame[0, 0])))
        source.send(1)
        self.assertTrue(wait_until(lambda: out))
        self.assertEqual(out, [6])


class TestShutdown(RackTestCase):

    def test_deleting_the_rack_stops_the_pipeline(self):
        parent = QtWidgets.QWidget()
        rack = self.make(parent=parent)
        pipeline = rack.pipeline
        parent.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        self.assertFalse(pipeline.isRunning())

    def test_quitting_the_application_stops_the_pipeline(self):
        rack = self.make()
        app.aboutToQuit.emit()
        self.assertFalse(rack.pipeline.isRunning())

    def test_closing_a_window_only_hides_the_rack(self):
        parent = QtWidgets.QWidget()
        rack = self.make(parent=parent)
        parent.show()
        parent.close()
        self.assertTrue(rack.pipeline.isRunning())


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
