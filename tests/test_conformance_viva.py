'''Conformance of the viva-genicam camera, on a simulated USB3 Vision device.

The device is the in-process fake camera of ``viva_genicam.testing``, so
the whole path runs: the node map, the properties, the stream.
'''
import unittest
from QVideo.tests.conformance import CameraConformance

try:
    from viva_genicam.testing import FakeU3vCamera
    from QVideo.cameras.Viva import QVivaCamera
except ImportError:  # pragma: no cover
    FakeU3vCamera = None


class SimulatedCamera(QVivaCamera):

    '''A camera that connects to a fake device.'''

    def _connect(self):
        return FakeU3vCamera(width=640, height=480).connect()


@unittest.skipIf(FakeU3vCamera is None, 'viva-genicam is not installed')
class TestVivaCameraConforms(CameraConformance, unittest.TestCase):

    def makeCamera(self):
        return SimulatedCamera()


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
