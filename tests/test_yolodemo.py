'''Unit tests for demos.yolodemo.'''
import unittest
from unittest.mock import MagicMock, patch
from qtpy import QtCore, QtWidgets
import QVideo.overlays.yolo as _yolo_mod
from QVideo.cameras.Noise._tree import QNoiseTree
from QVideo.demos.demo import Demo
from QVideo.demos.yolodemo import YoloDemo
from QVideo.overlays.yolo import QYoloWidget, _YoloWorker


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def make_demo():
    with patch.object(_yolo_mod, 'YOLO', MagicMock()), \
         patch.object(_YoloWorker, 'moveToThread'), \
         patch.object(QtCore.QThread, 'start'):
        return YoloDemo(QNoiseTree())


class TestYoloDemoInit(unittest.TestCase):

    def test_creates_successfully(self):
        widget = make_demo()
        self.assertIsInstance(widget, YoloDemo)

    def test_is_subclass_of_demo(self):
        widget = make_demo()
        self.assertIsInstance(widget, Demo)

    def test_yolo_attribute_is_qyolowidget(self):
        widget = make_demo()
        self.assertIsInstance(widget.yolo, QYoloWidget)

    def test_yolo_source_connected_to_screen_source(self):
        widget = make_demo()
        self.assertIs(widget.yolo.source, widget.screen.source)

    def test_custom_model_name_accepted(self):
        with patch.object(_yolo_mod, 'YOLO', MagicMock()), \
             patch.object(_YoloWorker, 'moveToThread'), \
             patch.object(QtCore.QThread, 'start'):
            widget = YoloDemo(QNoiseTree(), model_name='yolo11s.pt')
        self.assertIsInstance(widget, YoloDemo)

    def test_controls_contains_yolo_widget(self):
        widget = make_demo()
        items = [widget._controls.itemAt(i).widget()
                 for i in range(widget._controls.count())]
        self.assertIn(widget.yolo, items)

    def test_overlay_added_to_screen(self):
        widget = make_demo()
        self.assertIn(widget.yolo.overlay, widget.screen._overlays)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
