'''Conformance of a camera in a process of its own.'''
import sys
import unittest
from QVideo.lib import QRemoteCamera
from QVideo.tests.conformance import CameraConformance


@unittest.skipIf(sys.platform == 'win32', 'not available on Windows yet')
class TestRemoteCameraConforms(CameraConformance, unittest.TestCase):

    '''The noise camera, in a process of its own, keeps the contract.'''

    def makeCamera(self):
        return QRemoteCamera('noise')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
