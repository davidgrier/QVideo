'''Conformance of the GenICam camera, on a simulated device.

The device is the mock of ``test_qgenicamcamera``, given a small node map
with the nodes that every GenICam camera has: the frame size, a frame
rate and a gain.  The camera class is the real one.
'''
import sys
import unittest
from unittest.mock import MagicMock
from QVideo.tests.conformance import CameraConformance
from QVideo.tests import test_qgenicamcamera as support

MODULE = sys.modules['QVideo.cameras.Genicam._camera']


def node_map():
    '''Return the features of the simulated camera.'''
    integer = dict(min=64, max=1920, inc=4)
    width = support._make_feature(
        support._IInteger, 'Width', value=640, **integer)
    height = support._make_feature(
        support._IInteger, 'Height', value=480, **integer)
    rate = support._make_feature(
        support._IFloat, 'AcquisitionFrameRate', value=30., min=1., max=100.)
    rate.has_inc.return_value = False
    gain = support._make_feature(
        support._IFloat, 'Gain', value=1., min=0., max=24.)
    gain.has_inc.return_value = False
    return [width, height, rate, gain]


class TestGenicamCameraConforms(CameraConformance, unittest.TestCase):

    def makeCamera(self):
        device = support._make_device()
        root = MagicMock(spec=support._ICategory)
        root.features = node_map()
        device.remote_device.node_map.get_node.return_value = root
        camera, _, _ = support.make_camera(device=device)
        return camera


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
