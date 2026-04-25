'''Raspberry Pi camera backend via picamera2.

Supports all CSI-connected camera modules on a Raspberry Pi SBC,
including the HQ Camera, Camera Module 3, and compatible sensors.
Frames are delivered as RGB arrays.

Requires the ``picamera2`` package, which is pre-installed on
Raspberry Pi OS.  Install manually with::

    pip install picamera2

Classes
-------
QPicamera
    Camera backed by the Raspberry Pi camera module via picamera2.
QPicameraSource
    Threaded video source backed by :class:`QPicamera`.
QPicameraTree
    Parameter tree widget for :class:`QPicamera` controls.
'''
from ._camera import QPicamera, QPicameraSource
from ._tree import QPicameraTree


__all__ = 'QPicamera QPicameraSource QPicameraTree'.split()
