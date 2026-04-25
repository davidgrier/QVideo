'''Synthetic noise camera for testing and development.

Provides a hardware-free camera backend that generates random-noise
frames.  Use this backend to develop and test QVideo applications
without physical camera hardware.  It is also the reference
implementation for writing new camera backends.

Classes
-------
QNoiseCamera
    Camera that generates random noise frames.
QNoiseSource
    Threaded video source backed by :class:`QNoiseCamera`.
QNoiseTree
    Parameter tree widget for :class:`QNoiseCamera` controls.
'''
from ._camera import QNoiseCamera, QNoiseSource
from ._tree import QNoiseTree


__all__ = 'QNoiseCamera QNoiseSource QNoiseTree'.split()
