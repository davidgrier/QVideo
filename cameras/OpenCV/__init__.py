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
QOpenCVTree
    Parameter tree widget for :class:`QOpenCVCamera` controls.
QOpenCVDevices
    Utility class for probing connected OpenCV-accessible devices.
'''
from ._camera import QOpenCVCamera
from ._tree import QOpenCVTree
from ._devices import QOpenCVDevices
from QVideo.cameras._deprecated import deprecated_sources

#: The retired ``Q<Name>Source`` classes, until the next major release.
__getattr__ = deprecated_sources(__name__, QOpenCVSource=QOpenCVCamera)

__all__ = 'QOpenCVCamera QOpenCVTree QOpenCVDevices'.split()
