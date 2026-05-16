'''Unit tests for QHistogramWidget.'''
import unittest
from qtpy import QtWidgets
import pyqtgraph as pg
from QVideo.lib.QHistogramWidget import QHistogramWidget
from QVideo.lib.QVideoScreen import QVideoScreen


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class TestQHistogramWidgetConstruction(unittest.TestCase):

    def test_instantiates_without_screen(self):
        w = QHistogramWidget()
        self.assertIsInstance(w, QHistogramWidget)

    def test_is_histogram_lut_widget(self):
        w = QHistogramWidget()
        self.assertIsInstance(w, pg.HistogramLUTWidget)

    def test_screen_is_none_by_default(self):
        w = QHistogramWidget()
        self.assertIsNone(w.screen)

    def test_instantiates_with_screen(self):
        screen = QVideoScreen()
        w = QHistogramWidget(screen)
        self.assertIsInstance(w, QHistogramWidget)


class TestQHistogramWidgetScreen(unittest.TestCase):

    def setUp(self):
        self.screen = QVideoScreen()
        self.widget = QHistogramWidget()

    def test_screen_setter_stores_screen(self):
        self.widget.screen = self.screen
        self.assertIs(self.widget.screen, self.screen)

    def test_constructor_stores_screen(self):
        w = QHistogramWidget(self.screen)
        self.assertIs(w.screen, self.screen)

    def test_connected_image_item_is_screen_image(self):
        self.widget.screen = self.screen
        self.assertIs(self.widget.item.imageItem(), self.screen.image)

    def test_constructor_connects_image_item(self):
        w = QHistogramWidget(self.screen)
        self.assertIs(w.item.imageItem(), self.screen.image)

    def test_screen_can_be_replaced(self):
        other = QVideoScreen()
        self.widget.screen = self.screen
        self.widget.screen = other
        self.assertIs(self.widget.screen, other)
        self.assertIs(self.widget.item.imageItem(), other.image)


if __name__ == '__main__':
    unittest.main()
