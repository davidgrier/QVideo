'''Raspberry Pi camera backend via picamera2.

Supports all CSI-connected camera modules on a Raspberry Pi SBC,
including the HQ Camera, Camera Module 3, compatible sensors, and the
AI Camera (IMX500).  Frames are delivered as BGR arrays.

Requires the ``picamera2`` package, which is pre-installed on
Raspberry Pi OS.  Install manually with::

    pip install picamera2

For AI Camera (IMX500) support::

    pip install "picamera2[imx500]"

Classes
-------
QPicamera
    Camera backed by the Raspberry Pi camera module via picamera2.
QPicameraTree
    Parameter tree widget for :class:`QPicamera` controls.
QIMXCamera
    Camera backed by the Raspberry Pi AI Camera (IMX500).
'''
from ._camera import QPicamera
from ._imx500 import QIMXCamera
from ._tree import QPicameraTree
from QVideo.cameras._deprecated import deprecated_sources

#: The retired ``Q<Name>Source`` classes, until the next major release.
__getattr__ = deprecated_sources(
    __name__,
    QPicameraSource=QPicamera,
    QIMXSource=QIMXCamera)

__all__ = 'QPicamera QIMXCamera QPicameraTree'.split()
