'''Unit tests for vendor-specific QGenicamTree subclasses.

Covers the __init__ body of QBaslerTree, QFlirTree, QIDSTree,
QMVTree, and QVimbaXTree by instantiating each with a mocked camera.
'''
import sys
import unittest
import numpy as np
from unittest.mock import MagicMock, patch
from qtpy import QtWidgets

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

# ---------------------------------------------------------------------------
# Genicam stubs — EVisibility must be a real Python type so that
# QGenicamTree's @pyqtProperty(EVisibility) decorator works at class-
# definition time.
# ---------------------------------------------------------------------------

class _EVisibility(int): pass
_EVisibility.Beginner  = _EVisibility(0)
_EVisibility.Expert    = _EVisibility(1)
_EVisibility.Guru      = _EVisibility(2)
_EVisibility.Invisible = _EVisibility(99)


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


_mock_genapi = MagicMock()
_mock_genapi.EVisibility  = _EVisibility
_mock_genapi.IValue       = _IValue
_mock_genapi.ICategory    = _ICategory
_mock_genapi.ICommand     = _ICommand
_mock_genapi.IEnumeration = _IEnumeration
_mock_genapi.IBoolean     = _IBoolean
_mock_genapi.IInteger     = _IInteger
_mock_genapi.IFloat       = _IFloat
_mock_genapi.IString      = _IString
_mock_genapi.EAccessMode  = _EAccessMode
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

# Ensure the already-loaded genapi has a proper EVisibility type.
sys.modules['genicam.genapi'].EVisibility = _EVisibility

from QVideo.cameras.Basler._camera  import QBaslerCamera   # noqa: E402
from QVideo.cameras.Basler._tree   import QBaslerTree   # noqa: E402
from QVideo.cameras.Flir._camera   import QFlirCamera   # noqa: E402
from QVideo.cameras.Flir._tree     import QFlirTree     # noqa: E402
from QVideo.cameras.IDS._camera    import QIDSCamera    # noqa: E402
from QVideo.cameras.IDS._tree      import QIDSTree      # noqa: E402
from QVideo.cameras.MV._camera     import QMVCamera     # noqa: E402
from QVideo.cameras.MV._tree       import QMVTree       # noqa: E402
from QVideo.cameras.Vimbax._camera import QVimbaXCamera # noqa: E402
from QVideo.cameras.Vimbax._tree   import QVimbaXTree   # noqa: E402

_cam_module = sys.modules['QVideo.cameras.Genicam._camera']
_PRODUCER   = '/fake/producer.cti'


def _make_device():
    image = MagicMock()
    image.height = 480
    image.width  = 640
    image.num_components_per_pixel = 1
    image.data = np.zeros(480 * 640, dtype=np.uint8)
    buf = MagicMock()
    buf.payload.components = [image]
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=buf)
    cm.__exit__  = MagicMock(return_value=False)
    device = MagicMock()
    device.is_valid.return_value     = True
    device.is_acquiring.return_value = False
    device.fetch.return_value        = cm
    return device


def make_camera(CameraClass):
    '''Return an open CameraClass instance backed by a mocked device.'''
    device    = _make_device()
    harvester = MagicMock()
    harvester.create.return_value = device
    with patch.object(CameraClass, 'producer', _PRODUCER), \
         patch.object(_cam_module, 'Harvester', return_value=harvester):
        cam = CameraClass()
    return cam


# ---------------------------------------------------------------------------
# QBaslerTree
# ---------------------------------------------------------------------------

class TestQBaslerTree(unittest.TestCase):

    def setUp(self):
        self.cam = make_camera(QBaslerCamera)

    def tearDown(self):
        self.cam.close()

    def test_creates_with_camera(self):
        tree = QBaslerTree(camera=self.cam)
        self.assertIsInstance(tree, QBaslerTree)

    def test_accepts_custom_controls(self):
        tree = QBaslerTree(camera=self.cam, controls=['Gain'])
        self.assertIsInstance(tree, QBaslerTree)


# ---------------------------------------------------------------------------
# QFlirTree
# ---------------------------------------------------------------------------

class TestQFlirTree(unittest.TestCase):

    def setUp(self):
        self.cam = make_camera(QFlirCamera)

    def tearDown(self):
        self.cam.close()

    def test_creates_with_camera(self):
        tree = QFlirTree(camera=self.cam)
        self.assertIsInstance(tree, QFlirTree)

    def test_accepts_custom_controls(self):
        tree = QFlirTree(camera=self.cam, controls=['Gain'])
        self.assertIsInstance(tree, QFlirTree)


# ---------------------------------------------------------------------------
# QIDSTree
# ---------------------------------------------------------------------------

class TestQIDSTree(unittest.TestCase):

    def setUp(self):
        self.cam = make_camera(QIDSCamera)

    def tearDown(self):
        self.cam.close()

    def test_creates_with_camera(self):
        tree = QIDSTree(camera=self.cam)
        self.assertIsInstance(tree, QIDSTree)


# ---------------------------------------------------------------------------
# QMVTree
# ---------------------------------------------------------------------------

class TestQMVTree(unittest.TestCase):

    def setUp(self):
        self.cam = make_camera(QMVCamera)

    def tearDown(self):
        self.cam.close()

    def test_creates_with_camera(self):
        tree = QMVTree(camera=self.cam)
        self.assertIsInstance(tree, QMVTree)


# ---------------------------------------------------------------------------
# QVimbaXTree
# ---------------------------------------------------------------------------

class TestQVimbaXTree(unittest.TestCase):

    def setUp(self):
        self.cam = make_camera(QVimbaXCamera)

    def tearDown(self):
        self.cam.close()

    def test_creates_with_camera(self):
        tree = QVimbaXTree(camera=self.cam)
        self.assertIsInstance(tree, QVimbaXTree)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
