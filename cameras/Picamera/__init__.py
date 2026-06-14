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
QPicameraSource
    Threaded video source backed by :class:`QPicamera`.
QPicameraTree
    Parameter tree widget for :class:`QPicamera` controls.
QIMXCamera
    Camera backed by the Raspberry Pi AI Camera (IMX500).
QIMXSource
    Threaded video source backed by :class:`QIMXCamera`.
'''
from ._camera import QPicamera, QPicameraSource
from ._imx500 import QIMXCamera, QIMXSource
from ._tree import QPicameraTree


__all__ = 'QPicamera QPicameraSource QIMXCamera QIMXSource QPicameraTree'.split()
