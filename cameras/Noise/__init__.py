'''Synthetic noise camera for testing and development.

Provides a hardware-free camera backend that generates random-noise
frames.  Use this backend to develop and test QVideo applications
without physical camera hardware.  It is also the reference
implementation for writing new camera backends.

Classes
-------
QNoiseCamera
    Camera that generates random noise frames.
QNoiseTree
    Parameter tree widget for :class:`QNoiseCamera` controls.
'''
from ._camera import QNoiseCamera
from ._tree import QNoiseTree
from QVideo.cameras._deprecated import deprecated_sources

#: The retired ``Q<Name>Source`` classes, until the next major release.
__getattr__ = deprecated_sources(__name__, QNoiseSource=QNoiseCamera)

__all__ = 'QNoiseCamera QNoiseTree'.split()
