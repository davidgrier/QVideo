'''Conformance of the OpenCV camera, playing a video file as a camera.

The camera's own capture backend (AVFoundation, V4L2, MSMF) opens devices,
not files, so the test asks OpenCV for any backend that can read the file.
Everything else is the real camera class.
'''
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
import cv2
import QVideo
from QVideo.cameras.OpenCV._camera import QOpenCVCamera
from QVideo.tests.conformance import CameraConformance

VIDEO = Path(QVideo.__file__).parent / 'docs' / 'diatom3.avi'
MODULE = sys.modules['QVideo.cameras.OpenCV._camera']


class TestOpenCVCameraConforms(CameraConformance, unittest.TestCase):

    def makeCamera(self):
        patcher = patch.object(MODULE, 'capture_backend',
                               return_value=cv2.CAP_ANY)
        patcher.start()
        self.addCleanup(patcher.stop)
        return QOpenCVCamera(cameraID=str(VIDEO))


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
