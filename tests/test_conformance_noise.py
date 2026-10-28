'''Conformance of the noise camera.'''
import unittest
from QVideo.cameras.Noise._camera import QNoiseCamera
from QVideo.tests.conformance import CameraConformance


class TestNoiseCameraConforms(CameraConformance, unittest.TestCase):

    def makeCamera(self):
        return QNoiseCamera()


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
