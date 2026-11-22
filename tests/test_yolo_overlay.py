'''Unit tests for the YOLO object-detection overlay.'''
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import numpy as np
import pandas as pd
from qtpy import QtCore, QtWidgets


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from QVideo.tests.signals import record
import QVideo.overlays.yolo as _mod  # noqa: E402
from QVideo.overlays.yolo import (  # noqa: E402
    _YoloWorker, QYoloOverlay, QYoloWidget, decode, COCO_NAMES,
)
from QVideo.lib.dnn import DNN  # noqa: E402
from QVideo.tests.onnxfile import writeIdentity  # noqa: E402

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_frame() -> np.ndarray:
    return np.zeros((64, 64, 3), dtype=np.uint8)


def _make_features(n: int = 2) -> pd.DataFrame:
    return pd.DataFrame({
        'x1': [10., 30.],
        'y1': [10., 30.],
        'x2': [20., 50.],
        'y2': [20., 50.],
        'confidence': [0.9, 0.7],
        'class': [0, 1],
        'label': ['cat', 'dog'],
    })[:n]


class MockSource(QtCore.QObject):
    newFrame = QtCore.Signal(np.ndarray)


_directory = tempfile.TemporaryDirectory()
_path = str(writeIdentity(Path(_directory.name) / 'yolo.onnx',
                          (1, 3, 64, 64)))


def _make_widget(**kwargs):
    '''Create a QYoloWidget with the background thread neutralized.'''
    kwargs.setdefault('model_name', _path)
    kwargs.setdefault('imgsz', 64)
    with patch.object(_YoloWorker, 'moveToThread'), \
         patch.object(QtCore.QThread, 'start'):
        w = QYoloWidget(**kwargs)
    return w


# ---------------------------------------------------------------------------
# _YoloWorker
# ---------------------------------------------------------------------------

class TestYoloWorkerInit(unittest.TestCase):

    def test_loads_the_network_with_opencv(self):
        worker = _YoloWorker(model_name=_path, imgsz=64)
        self.assertIsInstance(worker.model, DNN)
        self.assertEqual(worker.model.size, (64, 64))

    def test_raises_when_pandas_missing(self):
        with patch.object(_mod, 'pd', None):
            with self.assertRaises(ImportError):
                _YoloWorker(model_name=_path, imgsz=64)

    def test_a_missing_file_raises_and_says_what_to_do(self):
        with self.assertRaises(FileNotFoundError) as caught:
            _YoloWorker(model_name='nothing.onnx')
        self.assertIn('export', str(caught.exception))

    def test_a_pt_file_is_refused_with_the_way_to_export_it(self):
        with self.assertRaises(ValueError) as caught:
            _YoloWorker(model_name='yolo11n.pt')
        self.assertIn('export', str(caught.exception))
        self.assertIn('onnx', str(caught.exception))

    def test_the_backend_is_gone(self):
        with self.assertRaises(TypeError):
            _YoloWorker(model_name=_path, backend='opencv')

    def test_importing_the_module_does_not_import_ultralytics(self):
        import subprocess
        import sys
        code = ('import sys\n'
                'import QVideo.overlays.yolo\n'
                'print("ultralytics" in sys.modules)')
        done = subprocess.run([sys.executable, '-c', code],
                              capture_output=True, text=True, timeout=120)
        self.assertEqual(done.stdout.strip(), 'False', done.stderr)


class TestYoloWorkerFailures(unittest.TestCase):

    def setUp(self):
        self._worker = _YoloWorker(model_name=_path, imgsz=64)
        self._worker.model = MagicMock(size=(64, 64))
        self._worker.model.forward.side_effect = RuntimeError('oops')

    def test_the_first_failure_is_logged_with_its_traceback(self):
        with self.assertLogs(_mod.logger, 'WARNING') as logs:
            self._worker.process(_make_frame())
        self.assertEqual(len(logs.records), 1)
        self.assertIsNotNone(logs.records[0].exc_info)

    def test_the_failures_that_follow_are_not_warnings(self):
        self._worker.process(_make_frame())
        with self.assertNoLogs(_mod.logger, 'WARNING'):
            self._worker.process(_make_frame())

    def test_a_failure_after_a_success_is_reported_again(self):
        self._worker.process(_make_frame())
        self._worker.model.forward.side_effect = None
        self._worker.model.forward.return_value = [
            _output((32, 32, 16, 16, 0.9, 0.1))]
        self._worker.process(_make_frame())
        self._worker.model.forward.side_effect = RuntimeError('again')
        with self.assertLogs(_mod.logger, 'WARNING'):
            self._worker.process(_make_frame())


# ---------------------------------------------------------------------------
# QYoloOverlay
# ---------------------------------------------------------------------------

class TestQYoloOverlay(unittest.TestCase):

    def setUp(self):
        self._overlay = QYoloOverlay()

    def test_bounding_rect_is_nonempty(self):
        rect = self._overlay.boundingRect()
        self.assertGreater(rect.width(), 0)
        self.assertGreater(rect.height(), 0)

    def test_set_features_stores_data(self):
        features = _make_features(2)
        self._overlay.setFeatures(features)
        self.assertIs(self._overlay._features, features)

    def test_set_features_none_clears(self):
        self._overlay.setFeatures(_make_features())
        self._overlay.setFeatures(None)
        self.assertIsNone(self._overlay._features)


def _render(overlay, size=(200, 100), shape=(100, 200)):
    '''Paint *overlay* on a black image and return its pixels.'''
    from qtpy import QtGui
    image = QtGui.QImage(size[0], size[1], QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor('black'))
    painter = QtGui.QPainter(image)
    overlay.paint(painter, None)
    painter.end()
    ptr = image.constBits()
    ptr.setsize(image.sizeInBytes())
    pixels = np.frombuffer(ptr, np.uint8).reshape(size[1], size[0], 4)
    return pixels[..., :3].copy()


def _one_box():
    return pd.DataFrame({'x1': [50.], 'y1': [50.], 'x2': [150.],
                         'y2': [90.], 'confidence': [0.9], 'class': [0],
                         'label': ['cat']})


class TestQYoloOverlayLabels(unittest.TestCase):

    def test_labels_are_on_by_default(self):
        self.assertTrue(QYoloOverlay().labels)

    def test_labels_can_start_off(self):
        self.assertFalse(QYoloOverlay(labels=False).labels)

    def test_the_setter_stores_a_bool(self):
        overlay = QYoloOverlay()
        overlay.labels = 0
        self.assertIs(overlay.labels, False)

    def test_a_label_is_drawn_above_the_box(self):
        overlay = QYoloOverlay()
        overlay.setFeatures(_one_box())
        pixels = _render(overlay)
        tab = pixels[36:49, 52:60]              # just above the box
        self.assertTrue((tab[..., 1] > 0).any())

    def test_nothing_is_drawn_above_the_box_without_labels(self):
        overlay = QYoloOverlay(labels=False)
        overlay.setFeatures(_one_box())
        pixels = _render(overlay)
        self.assertEqual(int(pixels[:48].max()), 0)

    def test_the_label_goes_inside_a_box_at_the_top_edge(self):
        box = _one_box()
        box[['y1', 'y2']] = (2., 40.)
        overlay = QYoloOverlay()
        overlay.setFeatures(box)
        pixels = _render(overlay)
        inside = pixels[4:14, 52:58]
        self.assertTrue((inside[..., 1] > 0).any())

    def test_painting_with_no_detections_is_harmless(self):
        overlay = QYoloOverlay()
        self.assertEqual(int(_render(overlay).max()), 0)
        overlay.setFeatures(None)
        self.assertEqual(int(_render(overlay).max()), 0)


# ---------------------------------------------------------------------------
# QYoloWidget
# ---------------------------------------------------------------------------

class TestQYoloWidgetInit(unittest.TestCase):

    def test_initial_confidence_in_spinbox(self):
        w = _make_widget(confidence=0.5)
        self.assertAlmostEqual(w._confidenceSpinBox.value(), 0.5)


class TestQYoloWidgetLabels(unittest.TestCase):

    def test_labels_are_on_by_default(self):
        w = _make_widget()
        self.assertTrue(w.overlay.labels)
        self.assertTrue(w._labelsCheckBox.isChecked())

    def test_labels_can_start_off(self):
        w = _make_widget(labels=False)
        self.assertFalse(w.overlay.labels)
        self.assertFalse(w._labelsCheckBox.isChecked())

    def test_the_check_box_toggles_the_labels(self):
        w = _make_widget()
        w._labelsCheckBox.setChecked(False)
        self.assertFalse(w.overlay.labels)
        w._labelsCheckBox.setChecked(True)
        self.assertTrue(w.overlay.labels)


class TestQYoloWidgetOverlay(unittest.TestCase):

    def test_overlay_returns_qyolooverlay(self):
        w = _make_widget()
        self.assertIsInstance(w.overlay, QYoloOverlay)


class TestQYoloWidgetConfidence(unittest.TestCase):

    def test_set_confidence(self):
        w = _make_widget()
        w._setConfidence(0.6)
        self.assertAlmostEqual(w._worker.confidence, 0.6)


# ---------------------------------------------------------------------------
# detections
# ---------------------------------------------------------------------------

def _output(*rows) -> np.ndarray:
    '''Return a network output (1, 4 + classes, N) from rows of
    cx, cy, w, h and the scores of the classes.'''
    return np.array(rows, dtype=np.float32).T[None]


class TestDecode(unittest.TestCase):

    def test_a_candidate_becomes_a_box(self):
        out = _output((50, 40, 20, 10, 0.9, 0.1))
        boxes, scores, classes = decode(out, 0.25)
        np.testing.assert_allclose(boxes, [[40, 35, 60, 45]])
        np.testing.assert_allclose(scores, [0.9], rtol=1e-6)
        self.assertEqual(classes.tolist(), [0])

    def test_the_class_is_the_best_score(self):
        out = _output((50, 40, 20, 10, 0.1, 0.8))
        self.assertEqual(decode(out, 0.25)[2].tolist(), [1])

    def test_low_scores_are_dropped(self):
        out = _output((50, 40, 20, 10, 0.1, 0.2))
        boxes, scores, classes = decode(out, 0.25)
        self.assertEqual((len(boxes), len(scores), len(classes)), (0, 0, 0))

    def test_overlapping_boxes_are_merged_and_the_best_kept(self):
        out = _output((50, 50, 20, 20, 0.6, 0.), (51, 50, 20, 20, 0.9, 0.),
                      (200, 200, 20, 20, 0.5, 0.))
        boxes, scores, _ = decode(out, 0.25, iou=0.45)
        self.assertEqual(len(boxes), 2)
        self.assertAlmostEqual(float(scores.max()), 0.9, places=5)

    def test_boxes_return_to_the_pixels_of_the_image(self):
        out = _output((32, 32, 16, 16, 0.9, 0.))
        boxes, _, _ = decode(out, 0.25, scale=0.5, pad=(0., 16.))
        np.testing.assert_allclose(boxes, [[48, 16, 80, 48]])

    def test_boxes_are_clipped_to_the_image(self):
        out = _output((5, 5, 20, 20, 0.9, 0.))
        boxes, _, _ = decode(out, 0.25, shape=(100, 100))
        np.testing.assert_allclose(boxes, [[0, 0, 15, 15]])

    def test_the_transposed_layout_is_accepted(self):
        out = _output((50, 40, 20, 10, 0.9, 0.1)).transpose(0, 2, 1)
        boxes = decode(out, 0.25, transposed=True)[0]
        np.testing.assert_allclose(boxes, [[40, 35, 60, 45]])


class TestOpenCVWorker(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        cls.path = str(writeIdentity(Path(cls.dir.name) / 'yolo.onnx',
                                     (1, 3, 64, 64)))

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def _worker(self, **kwargs):
        return _YoloWorker(model_name=self.path, imgsz=64, **kwargs)

    def test_a_missing_onnx_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            _YoloWorker(model_name='nothing.onnx')

    def test_detections_are_emitted_in_image_pixels(self):
        worker = self._worker()
        out = _output((32, 32, 16, 16, 0.9, 0.1))
        image = np.zeros((64, 128, 3), np.uint8)    # scale 0.5, pad y 16
        spy = record(worker.newData)
        with patch.object(DNN, 'forward', return_value=[out]):
            worker.process(image)
        df = spy[0][0]
        self.assertEqual(list(df.columns), ['x1', 'y1', 'x2', 'y2',
                                            'confidence', 'class', 'label'])
        self.assertEqual(df[['x1', 'y1', 'x2', 'y2']].values.tolist(),
                         [[48., 16., 80., 48.]])
        self.assertEqual(df['class'].tolist(), [0])

    def test_no_detection_emits_none(self):
        worker = self._worker()
        spy = record(worker.newData)
        with patch.object(DNN, 'forward',
                          return_value=[_output((32, 32, 16, 16, 0., 0.))]):
            worker.process(np.zeros((64, 64, 3), np.uint8))
        self.assertIsNone(spy[0][0])

    def test_names_label_the_classes(self):
        worker = self._worker(names=['cell', 'bead'])
        out = _output((32, 32, 16, 16, 0.1, 0.9))
        spy = record(worker.newData)
        with patch.object(DNN, 'forward', return_value=[out]):
            worker.process(np.zeros((64, 64, 3), np.uint8))
        self.assertEqual(spy[0][0]['label'].tolist(), ['bead'])

    def test_unnamed_classes_are_labeled_by_number(self):
        worker = self._worker()
        out = _output((32, 32, 16, 16, 0.1, 0.9))
        spy = record(worker.newData)
        with patch.object(DNN, 'forward', return_value=[out]):
            worker.process(np.zeros((64, 64, 3), np.uint8))
        self.assertEqual(spy[0][0]['label'].tolist(), ['1'])

    def test_a_network_of_80_classes_gets_the_coco_names(self):
        worker = self._worker()
        row = [32, 32, 16, 16] + [0.] * 80
        row[4 + 16] = 0.9
        out = _output(tuple(row))
        spy = record(worker.newData)
        with patch.object(DNN, 'forward', return_value=[out]):
            worker.process(np.zeros((64, 64, 3), np.uint8))
        self.assertEqual(spy[0][0]['label'].tolist(), [COCO_NAMES[16]])
        self.assertEqual(COCO_NAMES[16], 'dog')

    def test_a_failure_emits_none(self):
        worker = self._worker()
        spy = record(worker.newData)
        with patch.object(DNN, 'forward', side_effect=RuntimeError('x')):
            worker.process(np.zeros((64, 64, 3), np.uint8))
        self.assertIsNone(spy[0][0])

    def test_the_real_network_runs(self):
        # The identity network returns the input image, not detections:
        # the output has the wrong layout, which is a failure that the
        # worker survives.
        worker = self._worker()
        spy = record(worker.newData)
        worker.process(np.zeros((64, 64, 3), np.uint8))
        self.assertEqual(len(spy), 1)

    def test_the_widget_passes_the_model_on(self):
        w = _make_widget(model_name=self.path, imgsz=64)
        self.assertIsInstance(w._worker.model, DNN)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
