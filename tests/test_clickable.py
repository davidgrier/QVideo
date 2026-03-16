'''Unit tests for clickable.'''
import unittest
from unittest.mock import MagicMock
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets
from pyqtgraph.Qt.QtCore import Qt
from QVideo.lib.clickable import clickable


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_CENTER = QtCore.QPoint(50, 15)
_OUTSIDE = QtCore.QPoint(200, 200)


def send_click(widget, pos: QtCore.QPoint) -> None:
    '''Send a MouseButtonPress + MouseButtonRelease at pos (local coords).'''
    for event_type in (QtCore.QEvent.Type.MouseButtonPress,
                       QtCore.QEvent.Type.MouseButtonRelease):
        event = QtGui.QMouseEvent(
            event_type,
            QtCore.QPointF(pos),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        QtWidgets.QApplication.sendEvent(widget, event)


def make_release_event(pos: QtCore.QPoint) -> QtGui.QMouseEvent:
    return QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseButtonRelease,
        QtCore.QPointF(pos),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def make_press_event(pos: QtCore.QPoint) -> QtGui.QMouseEvent:
    return QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseButtonPress,
        QtCore.QPointF(pos),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


class TestClickableReturn(unittest.TestCase):

    def test_returns_connectable_signal(self):
        widget = QtWidgets.QWidget()
        signal = clickable(widget)
        self.assertTrue(hasattr(signal, 'connect'))

    def test_signal_is_connectable(self):
        widget = QtWidgets.QWidget()
        signal = clickable(widget)
        handler = MagicMock()
        signal.connect(handler)  # should not raise


class TestClickInside(unittest.TestCase):

    def setUp(self):
        self.widget = QtWidgets.QLineEdit()
        self.widget.resize(100, 30)
        self.handler = MagicMock()
        clickable(self.widget).connect(self.handler)

    def test_click_inside_emits_signal(self):
        send_click(self.widget, _CENTER)
        self.handler.assert_called_once()

    def test_multiple_clicks_emit_multiple_times(self):
        send_click(self.widget, _CENTER)
        send_click(self.widget, _CENTER)
        self.assertEqual(self.handler.call_count, 2)


class TestClickOutside(unittest.TestCase):

    def setUp(self):
        self.widget = QtWidgets.QLineEdit()
        self.widget.resize(100, 30)
        self.handler = MagicMock()
        clickable(self.widget).connect(self.handler)

    def test_release_outside_rect_does_not_emit(self):
        QtWidgets.QApplication.sendEvent(self.widget, make_release_event(_OUTSIDE))
        self.handler.assert_not_called()


class TestNonClickEvents(unittest.TestCase):

    def setUp(self):
        self.widget = QtWidgets.QLineEdit()
        self.widget.resize(100, 30)
        self.handler = MagicMock()
        clickable(self.widget).connect(self.handler)

    def test_mouse_press_does_not_emit(self):
        QtWidgets.QApplication.sendEvent(self.widget, make_press_event(_CENTER))
        self.handler.assert_not_called()


if __name__ == '__main__':
    unittest.main()
