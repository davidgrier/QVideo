'''Unit tests for QBaslerCamera and QBaslerSource.'''
import sys
import unittest
import numpy as np
from unittest.mock import MagicMock, patch
from pyqtgraph.Qt import QtWidgets

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

# ---------------------------------------------------------------------------
# Stub the optional genicam / harvesters packages before importing the module
# under test.  Real subclassable types let isinstance() checks work.
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


class _TimeoutException(Exception):
    pass


class _EVisibility(int):
    pass


_EVisibility.Beginner  = _EVisibility(0)
_EVisibility.Expert    = _EVisibility(1)
_EVisibility.Guru      = _EVisibility(2)
_EVisibility.Invisible = _EVisibility(99)

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
_mock_genapi.IProperty    = (_IEnumeration, _IBoolean, _IInteger, _IFloat, _IString)

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

from QVideo.cameras.Genicam._camera import QGenicamCamera
from QVideo.cameras.Basler._camera import QBaslerCamera, QBaslerSource

_cam_module = sys.modules['QVideo.cameras.Genicam._camera']
_MODULE = sys.modules['QVideo.cameras.Basler._camera']
_ICategory = _cam_module.ICategory
_PRODUCER = '/fake/ProducerU3V.cti'


def _make_device():
    device = MagicMock()
    device.is_valid.return_value = True
    device.is_acquiring.return_value = True
    device.remote_device.node_map.DeviceModelName.value = 'TestBasler'
    device.remote_device.node_map.has_node.return_value = True
    root = MagicMock(spec=_ICategory)
    root.features = []
    device.remote_device.node_map.get_node.return_value = root
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


def make_camera(cameraID=0):
    device = _make_device()
    harvester = MagicMock()
    harvester.create.return_value = device
    with patch.object(QBaslerCamera, 'producer', _PRODUCER):
        with patch.object(_cam_module, 'Harvester', return_value=harvester):
            cam = QBaslerCamera(cameraID=cameraID)
    return cam, harvester, device


class TestAll(unittest.TestCase):

    def test_all_defined(self):
        self.assertTrue(hasattr(_MODULE, '__all__'))

    def test_all_contains_camera(self):
        self.assertIn('QBaslerCamera', _MODULE.__all__)

    def test_all_contains_source(self):
        self.assertIn('QBaslerSource', _MODULE.__all__)


class TestSubclass(unittest.TestCase):

    def test_is_genicam_subclass(self):
        self.assertTrue(issubclass(QBaslerCamera, QGenicamCamera))


class TestProducer(unittest.TestCase):

    def test_raises_without_producer(self):
        with patch.object(QBaslerCamera, 'producer', None):
            with self.assertRaises(TypeError):
                QBaslerCamera()

    def test_opens_with_mocked_hardware(self):
        cam, _, _ = make_camera()
        self.assertTrue(cam.isOpen())
        cam.close()

    def test_camera_id_default_zero(self):
        cam, h, _ = make_camera()
        h.create.assert_called_once_with(0)
        cam.close()

    def test_camera_id_forwarded(self):
        cam, h, _ = make_camera(cameraID=2)
        h.create.assert_called_once_with(2)
        cam.close()

    def test_producer_registered_with_harvester(self):
        _, h, _ = make_camera()
        h.add_file.assert_called_once_with(_PRODUCER)


class TestSource(unittest.TestCase):

    def test_source_wraps_provided_camera(self):
        cam, _, _ = make_camera()
        src = QBaslerSource(camera=cam)
        self.assertIs(src.source, cam)
        cam.close()

    def test_source_creates_camera_when_none(self):
        device = _make_device()
        harvester = MagicMock()
        harvester.create.return_value = device
        with patch.object(QBaslerCamera, 'producer', _PRODUCER):
            with patch.object(_cam_module, 'Harvester', return_value=harvester):
                src = QBaslerSource()
        self.assertIsInstance(src.source, QBaslerCamera)
        src.source.close()

    def test_source_forwards_camera_id(self):
        device = _make_device()
        harvester = MagicMock()
        harvester.create.return_value = device
        with patch.object(QBaslerCamera, 'producer', _PRODUCER):
            with patch.object(_cam_module, 'Harvester', return_value=harvester):
                src = QBaslerSource(cameraID=3)
        harvester.create.assert_called_once_with(3)
        src.source.close()


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
