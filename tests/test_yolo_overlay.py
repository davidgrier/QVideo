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

# Replace module-level YOLO with a mock so tests never touch real ultralytics.
mock_YOLO_cls = MagicMock()
_mod.YOLO = mock_YOLO_cls


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


def _make_mock_results(n: int = 2):
    '''Return a mock ultralytics Results list with n detections.'''
    boxes = MagicMock()
    boxes.__len__ = MagicMock(return_value=n)
    xyxy = np.array([[10, 10, 20, 20], [30, 30, 50, 50]], dtype=np.float32)[:n]
    conf = np.array([0.9, 0.7], dtype=np.float32)[:n]
    cls = np.array([0, 1], dtype=np.float32)[:n]
    boxes.xyxy.cpu().numpy.return_value = xyxy
    boxes.conf.cpu().numpy.return_value = conf
    boxes.cls.cpu().numpy.return_value = cls
    result = MagicMock()
    result.boxes = boxes
    result.names = {0: 'cat', 1: 'dog'}
    return [result]


class MockSource(QtCore.QObject):
    newFrame = QtCore.Signal(np.ndarray)


def _make_widget(**kwargs):
    '''Create a QYoloWidget with the background thread neutralized.'''
    with patch.object(_YoloWorker, 'moveToThread'), \
         patch.object(QtCore.QThread, 'start'):
        w = QYoloWidget(**kwargs)
    return w


# ---------------------------------------------------------------------------
# _YoloWorker
# ---------------------------------------------------------------------------

class TestYoloWorkerInit(unittest.TestCase):

    def setUp(self):
        mock_YOLO_cls.reset_mock()

    def test_loads_model(self):
        _YoloWorker()
        mock_YOLO_cls.assert_called_once_with('yolo11n.pt')

    def test_custom_model_name(self):
        _YoloWorker(model_name='yolo11s.pt')
        mock_YOLO_cls.assert_called_once_with('yolo11s.pt')

    def test_raises_when_pandas_missing(self):
        with patch.object(_mod, 'pd', None):
            with self.assertRaises(ImportError):
                _YoloWorker()

    def test_raises_when_yolo_missing(self):
        with patch.object(_mod, '_loadYOLO', return_value=None):
            with self.assertRaises(ImportError):
                _YoloWorker()

    def test_the_error_names_why_the_import_failed(self):
        broken = OSError('libtorch could not be loaded')
        with patch.object(_mod, '_loadYOLO', return_value=None), \
                patch.object(_mod, '_importError', broken):
            with self.assertRaises(ImportError) as caught:
                _YoloWorker()
        self.assertIs(caught.exception.__cause__, broken)

    def test_raises_on_missing_model_file(self):
        mock_YOLO_cls.side_effect = FileNotFoundError
        with self.assertRaises(FileNotFoundError):
            _YoloWorker()
        mock_YOLO_cls.side_effect = None


class TestYoloWorkerDetect(unittest.TestCase):

    def setUp(self):
        mock_YOLO_cls.reset_mock()
        self._worker = _YoloWorker()
        self._worker.model = MagicMock()

    def test_detect_emits_dataframe_on_detections(self):
        self._worker.model.return_value = _make_mock_results(2)
        spy = record(self._worker.newData)
        self._worker.process(_make_frame())
        self.assertEqual(len(spy), 1)
        features = spy[0][0]
        self.assertIsNotNone(features)
        self.assertEqual(len(features), 2)

    def test_detect_emits_none_on_no_detections(self):
        self._worker.model.return_value = _make_mock_results(0)
        spy = record(self._worker.newData)
        self._worker.process(_make_frame())
        self.assertEqual(len(spy), 1)
        self.assertIsNone(spy[0][0])

    def test_detect_emits_none_on_exception(self):
        self._worker.model.side_effect = RuntimeError('oops')
        spy = record(self._worker.newData)
        self._worker.process(_make_frame())
        self.assertEqual(len(spy), 1)
        self.assertIsNone(spy[0][0])

    def test_detect_dataframe_has_expected_columns(self):
        self._worker.model.return_value = _make_mock_results(1)
        spy = record(self._worker.newData)
        self._worker.process(_make_frame())
        features = spy[0][0]
        for col in ('x1', 'y1', 'x2', 'y2', 'confidence', 'class', 'label'):
            self.assertIn(col, features.columns)

    def test_detect_passes_confidence_to_model(self):
        self._worker.confidence = 0.5
        self._worker.model.return_value = _make_mock_results(0)
        self._worker.process(_make_frame())
        _, kwargs = self._worker.model.call_args
        self.assertEqual(kwargs['conf'], 0.5)


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
# the OpenCV backend
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


class TestLoadYOLO(unittest.TestCase):

    def test_importing_the_module_does_not_import_ultralytics(self):
        import subprocess
        import sys
        code = ('import sys\n'
                'import QVideo.overlays.yolo\n'
                'print("ultralytics" in sys.modules)')
        done = subprocess.run([sys.executable, '-c', code],
                              capture_output=True, text=True, timeout=120)
        self.assertEqual(done.stdout.strip(), 'False', done.stderr)

    def test_the_threads_of_opencv_are_put_back(self):
        import sys
        import types
        fake = types.ModuleType('ultralytics')
        fake.YOLO = MagicMock()

        def side_effect_of_the_import(count):
            calls.append(count)

        calls = []
        with patch.dict(sys.modules, {'ultralytics': fake}), \
                patch.object(_mod, 'YOLO', None), \
                patch.object(_mod.cv2, 'getNumThreads', return_value=7), \
                patch.object(_mod.cv2, 'setNumThreads',
                             side_effect=side_effect_of_the_import):
            cls = _mod._loadYOLO()
            _mod.YOLO = None            # do not leave the fake behind
        self.assertIs(cls, fake.YOLO)
        self.assertEqual(calls, [7])

    def test_a_failed_import_is_reported_not_raised(self):
        import sys
        with patch.dict(sys.modules, {'ultralytics': None}), \
                patch.object(_mod, 'YOLO', None):
            self.assertIsNone(_mod._loadYOLO())
        self.assertIsNotNone(_mod._importError)


class TestOpenCVWorker(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        cls.path = str(writeIdentity(Path(cls.dir.name) / 'yolo.onnx',
                                     (1, 3, 64, 64)))

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def setUp(self):
        mock_YOLO_cls.reset_mock()

    def _worker(self, **kwargs):
        return _YoloWorker(model_name=self.path, imgsz=64, **kwargs)

    def test_auto_chooses_opencv_for_an_onnx_file(self):
        worker = self._worker()
        self.assertEqual(worker.backend, 'opencv')
        self.assertIsInstance(worker.model, DNN)
        mock_YOLO_cls.assert_not_called()

    def test_auto_chooses_ultralytics_for_a_pt_file(self):
        self.assertEqual(_YoloWorker().backend, 'ultralytics')

    def test_opencv_does_not_need_ultralytics(self):
        with patch.object(_mod, 'YOLO', None), \
                patch.object(_mod, '_loadYOLO') as load:
            self.assertEqual(self._worker().backend, 'opencv')
        load.assert_not_called()

    def test_an_unknown_backend_raises(self):
        with self.assertRaises(ValueError):
            _YoloWorker(backend='tensorflow')

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

    def test_the_widget_passes_the_backend_on(self):
        w = _make_widget(model_name=self.path, imgsz=64)
        self.assertEqual(w._worker.backend, 'opencv')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
