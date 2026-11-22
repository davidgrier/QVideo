'''Unit tests for demos.yolodemo.'''
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from qtpy import QtCore, QtWidgets
from QVideo.cameras.Noise._tree import QNoiseTree
from QVideo.demos.demo import Demo
from QVideo.tests.onnxfile import writeIdentity
from QVideo.demos.yolodemo import YoloDemo, options
from QVideo.overlays.yolo import QYoloWidget, _YoloWorker


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


_directory = tempfile.TemporaryDirectory()
_path = str(writeIdentity(Path(_directory.name) / 'model.onnx',
                          (1, 3, 64, 64)))


def make_demo(**kwargs):
    with patch.object(_YoloWorker, 'moveToThread'), \
         patch.object(QtCore.QThread, 'start'):
        return YoloDemo(QNoiseTree(), model_name=_path, imgsz=64, **kwargs)


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

    def test_labels_option_reaches_the_overlay(self):
        widget = make_demo(labels=False)
        self.assertFalse(widget.yolo.overlay.labels)

    def test_controls_contains_yolo_widget(self):
        widget = make_demo()
        items = [widget._controls.itemAt(i).widget()
                 for i in range(widget._controls.count())]
        self.assertIn(widget.yolo, items)

    def test_overlay_added_to_screen(self):
        widget = make_demo()
        self.assertIn(widget.yolo.overlay, widget.screen._overlays)


class TestYoloDemoModel(unittest.TestCase):

    def test_the_model_is_described_to_the_worker(self):
        widget = make_demo(names=['a', 'b'])
        worker = widget.yolo._worker
        self.assertEqual(worker.imgsz, 64)
        self.assertEqual(worker.names, ['a', 'b'])


class TestOptions(unittest.TestCase):

    def test_defaults(self):
        self.assertEqual(options([]), dict(
            model_name='yolo11n.onnx', imgsz=640, labels=True,
            names=None))

    def test_the_model_and_its_description(self):
        got = options(['--model', 'cells.onnx', '--imgsz', '320',
                       '--names', 'cell,bead'])
        self.assertEqual(got, dict(
            model_name='cells.onnx', imgsz=320, labels=True,
            names=['cell', 'bead']))

    def test_labels_are_on_unless_turned_off(self):
        self.assertTrue(options([])['labels'])
        self.assertFalse(options(['--no-labels'])['labels'])

    def test_camera_flags_are_left_to_launch(self):
        self.assertEqual(options(['-c', '--model', 'a.onnx'])['model_name'],
                         'a.onnx')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
