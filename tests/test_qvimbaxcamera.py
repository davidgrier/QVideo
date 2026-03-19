'''Unit tests for QVimbaXCamera and QVimbaXSource.'''
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import numpy as np
from pyqtgraph.Qt import QtWidgets


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


# ---------------------------------------------------------------------------
# Stub genicam / harvesters before importing anything from the package.
# Uses setdefault so the stubs are shared with test_qgenicamcamera.py when
# both run in the same session.
# ---------------------------------------------------------------------------

class _IValue:                pass
class _ICategory(_IValue):    pass
class _ICommand(_IValue):     pass
class _IEnumeration(_IValue): pass
class _IBoolean(_IValue):     pass
class _IInteger(_IValue):     pass
class _IFloat(_IValue):       pass
class _IString(_IValue):      pass


class _EAccessMode:
    RW = 'RW'
    RO = 'RO'
    WO = 'WO'
    NI = 'NI'


class _EVisibility(int):
    pass

_EVisibility.Beginner  = _EVisibility(0)
_EVisibility.Expert    = _EVisibility(1)
_EVisibility.Guru      = _EVisibility(2)
_EVisibility.Invisible = _EVisibility(99)


class _TimeoutException(Exception):
    pass


_mock_genapi = MagicMock()
_mock_genapi.IValue       = _IValue
_mock_genapi.ICategory    = _ICategory
_mock_genapi.ICommand     = _ICommand
_mock_genapi.IEnumeration = _IEnumeration
_mock_genapi.IBoolean     = _IBoolean
_mock_genapi.IInteger     = _IInteger
_mock_genapi.IFloat       = _IFloat
_mock_genapi.IString      = _IString
_mock_genapi.EAccessMode  = _EAccessMode
_mock_genapi.EVisibility  = _EVisibility
_mock_genapi.IProperty = _IEnumeration | _IBoolean | _IInteger | _IFloat | _IString

_mock_gentl                  = MagicMock()
_mock_gentl.TimeoutException = _TimeoutException

_mock_harvesters_core = MagicMock()
_mock_harvesters      = MagicMock()
_mock_harvesters.core = _mock_harvesters_core

for _name, _mod in [('harvesters',      _mock_harvesters),
                    ('harvesters.core', _mock_harvesters_core),
                    ('genicam',         MagicMock()),
                    ('genicam.genapi',  _mock_genapi),
                    ('genicam.gentl',   _mock_gentl)]:
    sys.modules.setdefault(_name, _mod)

# Import directly from the submodule to avoid pulling in QVimbaXTree
from QVideo.cameras.Genicam.QGenicamCamera import QGenicamCamera
from QVideo.cameras.Vimbax.QVimbaXCamera import QVimbaXCamera, QVimbaXSource

_cam_module = sys.modules['QVideo.cameras.Genicam.QGenicamCamera']

FAKE_PRODUCER = '/fake/VimbaUSBTL.cti'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_node_map():
    nm = MagicMock()
    nm.has_node.return_value = True
    root = MagicMock(spec=_ICategory)
    root.features = []
    nm.get_node.return_value = root
    return nm


def _make_device():
    device = MagicMock()
    device.is_valid.return_value = True
    device.is_acquiring.return_value = True
    device.remote_device.node_map = _make_node_map()
    image = MagicMock()
    image.height = 480
    image.width = 640
    image.num_components_per_pixel = 1
    image.data = np.zeros(480 * 640, dtype=np.uint8)
    buf = MagicMock()
    buf.payload.components = [image]
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=buf)
    cm.__exit__ = MagicMock(return_value=False)
    device.fetch.return_value = cm
    return device


def make_camera(cameraID=0, device=None):
    '''Return (camera, harvester_instance, device) with mocked hardware.'''
    if device is None:
        device = _make_device()
    harvester = MagicMock()
    harvester.create.return_value = device
    with patch.object(QVimbaXCamera, 'producer', FAKE_PRODUCER):
        with patch.object(_cam_module, 'Harvester', return_value=harvester):
            cam = QVimbaXCamera(cameraID=cameraID)
    return cam, harvester, device


# ---------------------------------------------------------------------------
# TestFindProducer
# ---------------------------------------------------------------------------

class TestFindProducer(unittest.TestCase):

    def test_returns_none_when_env_not_set(self):
        with patch.dict(os.environ, {}, clear=True):
            result = QGenicamCamera._find_producer('VimbaUSBTL.cti')
        self.assertIsNone(result)

    def test_returns_none_when_no_producer_files_found(self):
        with patch.dict(os.environ, {'GENICAM_GENTL64_PATH': '/no/such/dir'}):
            with patch.object(Path, 'exists', return_value=False):
                result = QGenicamCamera._find_producer('VimbaUSBTL.cti')
        self.assertIsNone(result)

    def test_returns_path_when_producer_exists(self):
        fake_dir = '/opt/VimbaX/lib'
        expected = str(Path(fake_dir) / 'VimbaUSBTL.cti')
        with patch.dict(os.environ, {'GENICAM_GENTL64_PATH': fake_dir}):
            with patch.object(Path, 'exists', return_value=True):
                result = QGenicamCamera._find_producer('VimbaUSBTL.cti')
        self.assertEqual(result, expected)

    def test_returns_string_not_path(self):
        fake_dir = '/opt/VimbaX/lib'
        with patch.dict(os.environ, {'GENICAM_GENTL64_PATH': fake_dir}):
            with patch.object(Path, 'exists', return_value=True):
                result = QGenicamCamera._find_producer('VimbaUSBTL.cti')
        self.assertIsInstance(result, str)

    def test_searches_multiple_directories(self):
        dir1, dir2 = '/dir/one', '/dir/two'
        expected = str(Path(dir2) / 'VimbaUSBTL.cti')

        def _exists(p):
            return str(p) == expected

        with patch.dict(os.environ,
                        {'GENICAM_GENTL64_PATH': os.pathsep.join([dir1, dir2])}):
            with patch.object(Path, 'exists', _exists):
                result = QGenicamCamera._find_producer('VimbaUSBTL.cti')
        self.assertEqual(result, expected)

    def test_first_filename_preferred(self):
        fake_dir = '/opt/VimbaX/lib'
        usb = str(Path(fake_dir) / 'VimbaUSBTL.cti')
        gige = str(Path(fake_dir) / 'VimbaGigETL.cti')

        def _exists(p):
            return str(p) in (usb, gige)

        with patch.dict(os.environ, {'GENICAM_GENTL64_PATH': fake_dir}):
            with patch.object(Path, 'exists', _exists):
                result = QGenicamCamera._find_producer(
                    'VimbaUSBTL.cti', 'VimbaGigETL.cti')
        self.assertEqual(result, usb)


# ---------------------------------------------------------------------------
# TestQVimbaXCamera
# ---------------------------------------------------------------------------

class TestQVimbaXCamera(unittest.TestCase):

    def test_is_genicam_camera_subclass(self):
        self.assertTrue(issubclass(QVimbaXCamera, QGenicamCamera))

    def test_producer_is_class_attribute(self):
        self.assertIn('producer', QVimbaXCamera.__dict__)

    def test_raises_type_error_when_producer_is_none(self):
        saved = QVimbaXCamera.producer
        try:
            QVimbaXCamera.producer = None
            with self.assertRaises(TypeError):
                QVimbaXCamera()
        finally:
            QVimbaXCamera.producer = saved

    def test_opens_on_init(self):
        cam, _, _ = make_camera()
        self.assertTrue(cam.isOpen())

    def test_camera_id_default_zero(self):
        cam, _, _ = make_camera()
        self.assertEqual(cam.cameraID, 0)

    def test_camera_id_forwarded(self):
        cam, _, _ = make_camera(cameraID=2)
        self.assertEqual(cam.cameraID, 2)

    def test_harvester_add_file_called_with_producer(self):
        _, h, _ = make_camera()
        h.add_file.assert_called_once_with(FAKE_PRODUCER)


# ---------------------------------------------------------------------------
# TestQVimbaXSource
# ---------------------------------------------------------------------------

class TestQVimbaXSource(unittest.TestCase):

    def test_uses_provided_camera(self):
        cam, _, _ = make_camera()
        src = QVimbaXSource(camera=cam)
        self.assertIs(src.source, cam)

    def test_creates_camera_when_none_given(self):
        device = _make_device()
        harvester = MagicMock()
        harvester.create.return_value = device
        with patch.object(QVimbaXCamera, 'producer', FAKE_PRODUCER):
            with patch.object(_cam_module, 'Harvester', return_value=harvester):
                src = QVimbaXSource()
        self.assertIsInstance(src.source, QVimbaXCamera)

    def test_forwards_camera_id(self):
        device = _make_device()
        harvester = MagicMock()
        harvester.create.return_value = device
        with patch.object(QVimbaXCamera, 'producer', FAKE_PRODUCER):
            with patch.object(_cam_module, 'Harvester', return_value=harvester):
                QVimbaXSource(cameraID=1)
        harvester.create.assert_called_once_with(1)


if __name__ == '__main__':
    unittest.main()
