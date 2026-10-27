'''Unit tests for QScrollPanel.'''
import unittest
from unittest.mock import patch
from qtpy import QtCore, QtTest, QtWidgets
from QVideo.lib import QScrollPanel

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def make_panel(rows: int = 30) -> QtWidgets.QWidget:
    panel = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(panel)
    for i in range(rows):
        layout.addWidget(QtWidgets.QLabel(f'control {i}'))
    return panel


class TestQScrollPanel(unittest.TestCase):

    def setUp(self):
        self.panel = make_panel()
        self.scroll = QScrollPanel(self.panel)
        self.addCleanup(self.scroll.deleteLater)

    def test_it_holds_the_panel(self):
        self.assertIs(self.scroll.widget(), self.panel)

    def test_the_hint_is_the_panel_with_room_for_the_bar(self):
        bar = self.scroll.style().pixelMetric(
            QtWidgets.QStyle.PixelMetric.PM_ScrollBarExtent)
        hint, wanted = self.scroll.sizeHint(), self.panel.sizeHint()
        self.assertEqual(hint.width(), wanted.width() + bar)
        self.assertEqual(hint.height(), wanted.height())

    def test_the_width_may_not_shrink_below_the_hint(self):
        self.assertEqual(self.scroll.minimumSizeHint().width(),
                         self.scroll.sizeHint().width())

    def test_the_minimum_height_is_short(self):
        self.assertLess(self.scroll.minimumSizeHint().height(),
                        self.scroll.sizeHint().height())

    def test_a_short_window_scrolls_vertically_and_never_sideways(self):
        self.scroll.resize(self.scroll.sizeHint().width(), 100)
        self.scroll.show()
        QtTest.QTest.qWait(50)
        bar = self.scroll.verticalScrollBar()
        self.assertGreater(bar.maximum(), 0)
        self.assertFalse(self.scroll.horizontalScrollBar().isVisible())

    def test_a_tall_window_does_not_scroll(self):
        self.scroll.resize(self.scroll.sizeHint())
        self.scroll.show()
        QtTest.QTest.qWait(50)
        self.assertEqual(self.scroll.verticalScrollBar().maximum(), 0)

    def test_a_panel_that_grows_asks_for_a_new_size(self):
        with patch.object(self.scroll, 'updateGeometry') as update:
            self.panel.layout().addWidget(QtWidgets.QLabel('one more'))
            QtCore.QCoreApplication.sendPostedEvents(
                self.panel, QtCore.QEvent.LayoutRequest)
            QtCore.QCoreApplication.sendEvent(
                self.panel, QtCore.QEvent(QtCore.QEvent.LayoutRequest))
        update.assert_called()

    def test_other_events_are_not_taken_for_a_new_size(self):
        with patch.object(self.scroll, 'updateGeometry') as update:
            QtCore.QCoreApplication.sendEvent(
                self.panel, QtCore.QEvent(QtCore.QEvent.User))
        update.assert_not_called()


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
