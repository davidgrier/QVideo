'''OpenCV camera backend for USB webcams and V4L2 devices.

Supports USB webcams and any device accessible via OpenCV's
``VideoCapture``.  On Linux the V4L2 backend is selected automatically;
all other platforms use ``CAP_ANY``.  No vendor SDK is required beyond
OpenCV itself.

Resolution and frame-rate selection modes (quality, performance, and
explicit) are described in :class:`QOpenCVCamera`.

Classes
-------
QOpenCVCamera
    Camera backed by OpenCV's ``VideoCapture``.
QOpenCVSource
    Threaded video source backed by :class:`QOpenCVCamera`.
QOpenCVTree
    Parameter tree widget for :class:`QOpenCVCamera` controls.
QOpenCVDevices
    Utility class for probing connected OpenCV-accessible devices.
'''
from ._camera import QOpenCVCamera, QOpenCVSource
from ._tree import QOpenCVTree
from ._devices import QOpenCVDevices


__all__ = 'QOpenCVCamera QOpenCVSource QOpenCVTree QOpenCVDevices'.split()
