'''Unit tests for QListCVCameras.'''
import sys
import importlib
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import cv2
from qtpy import QtWidgets
from QVideo.cameras.OpenCV.QListCVCameras import QListCVCameras, _probe_cameras
from QVideo.cameras.OpenCV._camera import QOpenCVCamera


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def make_fake_camera(name='Test Camera', index=0):
    '''Return a fake CameraInfo-like object as returned by enumerate_cameras.'''
    return SimpleNamespace(name=name, index=index)


def make_mock_capture(is_open=True, width=640, height=480):
    '''Return a MagicMock standing in for cv2.VideoCapture.'''
    cap = MagicMock()
    cap.isOpened.return_value = is_open
    cap.get.side_effect = lambda prop: {
        cv2.CAP_PROP_FRAME_WIDTH: float(width),
        cv2.CAP_PROP_FRAME_HEIGHT: float(height),
    }.get(prop, 0.0)
    return cap


# ---------------------------------------------------------------------------
# _model
# ---------------------------------------------------------------------------

class TestQListCVCamerasModel(unittest.TestCase):

    def test_model_returns_qopencvcamera(self):
        with patch('QVideo.cameras.OpenCV.QListCVCameras._enumerate_cameras',
                   return_value=[]):
            combo = QListCVCameras()
        self.assertIs(combo._model(), QOpenCVCamera)


# ---------------------------------------------------------------------------
# _listCameras — enumerate_cameras path
# ---------------------------------------------------------------------------

class TestEnumeratePath(unittest.TestCase):

    def test_no_cameras_gives_only_placeholder(self):
        with patch('QVideo.cameras.OpenCV.QListCVCameras._enumerate_cameras',
                   return_value=[]):
            combo = QListCVCameras()
        self.assertEqual(combo.count(), 1)

    def test_one_camera_adds_one_item(self):
        cameras = [make_fake_camera('My Camera', 0)]
        with patch('QVideo.cameras.OpenCV.QListCVCameras._enumerate_cameras',
                   return_value=cameras):
            combo = QListCVCameras()
        self.assertEqual(combo.count(), 2)

    def test_camera_label_format(self):
        cameras = [make_fake_camera('WebCam Pro', 2)]
        with patch('QVideo.cameras.OpenCV.QListCVCameras._enumerate_cameras',
                   return_value=cameras):
            combo = QListCVCameras()
        self.assertEqual(combo.itemText(1), 'WebCam Pro (Index: 2)')

    def test_camera_data_is_device_index(self):
        cameras = [make_fake_camera('WebCam Pro', 2)]
        with patch('QVideo.cameras.OpenCV.QListCVCameras._enumerate_cameras',
                   return_value=cameras):
            combo = QListCVCameras()
        self.assertEqual(combo.itemData(1), 2)

    def test_multiple_cameras_all_listed(self):
        cameras = [make_fake_camera('Camera A', 0),
                   make_fake_camera('Camera B', 1),
                   make_fake_camera('Camera C', 2)]
        with patch('QVideo.cameras.OpenCV.QListCVCameras._enumerate_cameras',
                   return_value=cameras):
            combo = QListCVCameras()
        self.assertEqual(combo.count(), 4)

    def test_multiple_cameras_correct_labels(self):
        cameras = [make_fake_camera('Camera A', 0),
                   make_fake_camera('Camera B', 1)]
        with patch('QVideo.cameras.OpenCV.QListCVCameras._enumerate_cameras',
                   return_value=cameras):
            combo = QListCVCameras()
        self.assertEqual(combo.itemText(1), 'Camera A (Index: 0)')
        self.assertEqual(combo.itemText(2), 'Camera B (Index: 1)')

    def test_non_contiguous_device_indices(self):
        cameras = [make_fake_camera('Camera A', 0),
                   make_fake_camera('Camera B', 3)]
        with patch('QVideo.cameras.OpenCV.QListCVCameras._enumerate_cameras',
                   return_value=cameras):
            combo = QListCVCameras()
        self.assertEqual(combo.itemData(1), 0)
        self.assertEqual(combo.itemData(2), 3)

    def test_placeholder_is_first_item(self):
        cameras = [make_fake_camera('Camera A', 0)]
        with patch('QVideo.cameras.OpenCV.QListCVCameras._enumerate_cameras',
                   return_value=cameras):
            combo = QListCVCameras()
        self.assertEqual(combo.itemText(0), 'Select Camera')
        self.assertEqual(combo.itemData(0), -1)

    def test_refresh_calls_enumerate_again(self):
        cameras = [make_fake_camera('Camera A', 0)]
        with patch('QVideo.cameras.OpenCV.QListCVCameras._enumerate_cameras',
                   return_value=cameras) as mock_enum:
            combo = QListCVCameras()
            combo.refresh()
        self.assertEqual(mock_enum.call_count, 2)


# ---------------------------------------------------------------------------
# _listCameras — probe fallback path
# ---------------------------------------------------------------------------

class TestProbeFallbackPath(unittest.TestCase):

    def _make_combo_with_probe(self, probe_results):
        with patch('QVideo.cameras.OpenCV.QListCVCameras._enumerate_cameras', None):
            with patch('QVideo.cameras.OpenCV.QListCVCameras._probe_cameras',
                       return_value=iter(probe_results)):
                return QListCVCameras()

    def test_no_cameras_gives_only_placeholder(self):
        combo = self._make_combo_with_probe([])
        self.assertEqual(combo.count(), 1)

    def test_probe_results_added_as_items(self):
        combo = self._make_combo_with_probe([('Camera 0 (640x480)', 0),
                                             ('Camera 1 (1280x720)', 1)])
        self.assertEqual(combo.count(), 3)

    def test_probe_label_used_as_item_text(self):
        combo = self._make_combo_with_probe([('Camera 0 (640x480)', 0)])
        self.assertEqual(combo.itemText(1), 'Camera 0 (640x480)')

    def test_probe_index_used_as_item_data(self):
        combo = self._make_combo_with_probe([('Camera 0 (640x480)', 0)])
        self.assertEqual(combo.itemData(1), 0)


# ---------------------------------------------------------------------------
# _probe_cameras
# ---------------------------------------------------------------------------

class TestProbeCameras(unittest.TestCase):

    def _make_cv2_mock(self, open_at=(0,), width=640, height=480):
        '''Return a VideoCapture constructor mock that opens only at given indices.'''
        def factory(index):
            cap = make_mock_capture(is_open=(index in open_at),
                                    width=width, height=height)
            return cap
        return factory

    def test_yields_nothing_when_no_cameras_open(self):
        with patch('QVideo.cameras.OpenCV.QListCVCameras.cv2.VideoCapture',
                   side_effect=self._make_cv2_mock(open_at=())):
            results = list(_probe_cameras())
        self.assertEqual(results, [])

    def test_yields_open_camera(self):
        with patch('QVideo.cameras.OpenCV.QListCVCameras.cv2.VideoCapture',
                   side_effect=self._make_cv2_mock(open_at=(0,))):
            results = list(_probe_cameras())
        self.assertEqual(len(results), 1)

    def test_label_includes_index_and_resolution(self):
        with patch('QVideo.cameras.OpenCV.QListCVCameras.cv2.VideoCapture',
                   side_effect=self._make_cv2_mock(open_at=(0,), width=1280, height=720)):
            label, index = next(_probe_cameras())
        self.assertEqual(label, 'Camera 0 (1280x720)')
        self.assertEqual(index, 0)

    def test_index_matches_probed_position(self):
        with patch('QVideo.cameras.OpenCV.QListCVCameras.cv2.VideoCapture',
                   side_effect=self._make_cv2_mock(open_at=(2,))):
            results = list(_probe_cameras())
        self.assertEqual(len(results), 1)
        _, index = results[0]
        self.assertEqual(index, 2)

    def test_multiple_open_cameras(self):
        with patch('QVideo.cameras.OpenCV.QListCVCameras.cv2.VideoCapture',
                   side_effect=self._make_cv2_mock(open_at=(0, 1, 3))):
            results = list(_probe_cameras())
        self.assertEqual(len(results), 3)
        self.assertEqual([i for _, i in results], [0, 1, 3])

    def test_log_level_restored_after_probe(self):
        with patch.object(cv2, 'getLogLevel', return_value=3, create=True), \
             patch.object(cv2, 'setLogLevel', create=True) as mock_set_log, \
             patch('QVideo.cameras.OpenCV.QListCVCameras.cv2.VideoCapture',
                   side_effect=self._make_cv2_mock(open_at=())):
            list(_probe_cameras())
        calls = [c.args[0] for c in mock_set_log.call_args_list]
        self.assertEqual(calls, [0, 3])

    def test_log_level_restored_on_exception(self):
        def bad_capture(i):
            raise RuntimeError('device error')
        with patch.object(cv2, 'getLogLevel', return_value=3, create=True), \
             patch.object(cv2, 'setLogLevel', create=True) as mock_set_log, \
             patch('QVideo.cameras.OpenCV.QListCVCameras.cv2.VideoCapture',
                   side_effect=bad_capture):
            try:
                list(_probe_cameras())
            except RuntimeError:
                pass
        calls = [c.args[0] for c in mock_set_log.call_args_list]
        self.assertEqual(calls[-1], 3)

    def test_release_called_for_closed_capture(self):
        closed_cap = make_mock_capture(is_open=False)
        with patch('QVideo.cameras.OpenCV.QListCVCameras.cv2.VideoCapture',
                   return_value=closed_cap):
            list(_probe_cameras())
        closed_cap.release.assert_called()

    def test_release_called_for_open_capture(self):
        open_cap = make_mock_capture(is_open=True)
        with patch('QVideo.cameras.OpenCV.QListCVCameras.cv2.VideoCapture',
                   return_value=open_cap):
            list(_probe_cameras())
        open_cap.release.assert_called()


# ---------------------------------------------------------------------------
# Import warning
# ---------------------------------------------------------------------------

class TestImportWarning(unittest.TestCase):

    def test_warns_when_cv2_enumerate_cameras_missing(self):
        mod_name = 'QVideo.cameras.OpenCV.QListCVCameras'
        saved_mod = sys.modules.pop(mod_name, None)
        try:
            with patch.dict(sys.modules, {'cv2_enumerate_cameras': None}):
                with self.assertWarns(ImportWarning):
                    importlib.import_module(mod_name)
        finally:
            if saved_mod is not None:
                sys.modules[mod_name] = saved_mod


if __name__ == '__main__':
    unittest.main()
