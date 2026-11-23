'''Unit tests for QUniformityWidget.'''
import unittest
import numpy as np
from qtpy import QtWidgets
import pyqtgraph as pg
from QVideo.widgets.QUniformityWidget import QUniformityWidget
from QVideo.lib.QVideoScreen import QVideoScreen


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_GRAY = np.random.randint(0, 256, (64, 80), dtype=np.uint8)
_COLOR = np.random.randint(0, 256, (64, 80, 3), dtype=np.uint8)


class TestQUniformityWidgetConstruction(unittest.TestCase):

    def test_instantiates_without_screen(self):
        w = QUniformityWidget()
        self.assertIsInstance(w, QUniformityWidget)

    def test_is_graphics_layout_widget(self):
        w = QUniformityWidget()
        self.assertIsInstance(w, pg.GraphicsLayoutWidget)

    def test_screen_is_none_by_default(self):
        w = QUniformityWidget()
        self.assertIsNone(w.screen)

    def test_instantiates_with_screen(self):
        screen = QVideoScreen()
        w = QUniformityWidget(screen)
        self.assertIsInstance(w, QUniformityWidget)


class TestQUniformityWidgetScreen(unittest.TestCase):

    def setUp(self):
        self.screen = QVideoScreen()
        self.widget = QUniformityWidget()

    def test_screen_setter_stores_screen(self):
        self.widget.screen = self.screen
        self.assertIs(self.widget.screen, self.screen)

    def test_constructor_stores_screen(self):
        w = QUniformityWidget(self.screen)
        self.assertIs(w.screen, self.screen)

    def test_newframe_connected_via_constructor(self):
        w = QUniformityWidget(self.screen)
        self.screen.newFrame.emit(_GRAY, None)
        _, y = w._xcurve.getData()
        self.assertIsNotNone(y)

    def test_newframe_connected_via_setter(self):
        self.widget.screen = self.screen
        self.screen.newFrame.emit(_GRAY, None)
        _, y = self.widget._xcurve.getData()
        self.assertIsNotNone(y)

    def test_old_screen_disconnected_on_replacement(self):
        other = QVideoScreen()
        self.widget.screen = self.screen
        self.widget.screen = other
        self.screen.newFrame.emit(_GRAY, None)
        _, y = self.widget._xcurve.getData()
        self.assertIsNone(y)

    def test_screen_replacement_stores_new_screen(self):
        other = QVideoScreen()
        self.widget.screen = self.screen
        self.widget.screen = other
        self.assertIs(self.widget.screen, other)


class TestQUniformityWidgetSetFrame(unittest.TestCase):

    def setUp(self):
        self.widget = QUniformityWidget()

    def test_grayscale_xcurve_length(self):
        self.widget.setFrame(_GRAY)
        _, y = self.widget._xcurve.getData()
        self.assertEqual(len(y), _GRAY.shape[1])

    def test_grayscale_ycurve_length(self):
        self.widget.setFrame(_GRAY)
        _, y = self.widget._ycurve.getData()
        self.assertEqual(len(y), _GRAY.shape[0])

    def test_color_traces_have_the_length_of_the_axes(self):
        self.widget.setFrame(_COLOR)
        for curves, n in ((self.widget._xcolor, _COLOR.shape[1]),
                          (self.widget._ycolor, _COLOR.shape[0])):
            for curve in curves:
                _, y = curve.getData()
                self.assertEqual(len(y), n)

    def test_uniform_image_flat_xcurve(self):
        image = np.full((8, 16), 100, dtype=np.uint8)
        self.widget.setFrame(image)
        _, y = self.widget._xcurve.getData()
        np.testing.assert_array_almost_equal(y, np.full(16, 100.0))

    def test_uniform_image_flat_ycurve(self):
        image = np.full((8, 16), 100, dtype=np.uint8)
        self.widget.setFrame(image)
        _, y = self.widget._ycurve.getData()
        np.testing.assert_array_almost_equal(y, np.full(8, 100.0))

    def test_color_has_a_trace_for_each_channel(self):
        image = np.zeros((4, 8, 3), dtype=np.uint8)
        image[:, :, 0] = 60   # R
        image[:, :, 1] = 120  # G
        image[:, :, 2] = 180  # B
        self.widget.setFrame(image)
        for curves in (self.widget._xcolor, self.widget._ycolor):
            for curve, value in zip(curves, (60, 120, 180), strict=True):
                _, y = curve.getData()
                np.testing.assert_allclose(y, value)

    def test_a_fourth_channel_is_not_plotted(self):
        image = np.zeros((4, 8, 4), dtype=np.uint8)
        self.widget.setFrame(image)
        self.assertEqual(len(self.widget._xcolor), 3)

    def test_gray_shows_one_trace_and_color_shows_three(self):
        self.widget.setFrame(_GRAY)
        self.assertTrue(self.widget._xcurve.isVisible())
        self.assertFalse(any(c.isVisible() for c in self.widget._xcolor))
        self.widget.setFrame(_COLOR)
        self.assertFalse(self.widget._xcurve.isVisible())
        self.assertTrue(all(c.isVisible() for c in self.widget._xcolor))


if __name__ == '__main__':
    unittest.main()
