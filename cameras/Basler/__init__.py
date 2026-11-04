'''Basler camera backend via the pylon GenTL producer.

Supports Basler USB3 Vision and GigE Vision cameras through
`pylon <https://www.baslerweb.com/en/software/pylon/>`_,
Basler's machine-vision SDK.  The pylon installer registers
GenTL producer paths in ``GENICAM_GENTL64_PATH``, which this
backend discovers automatically.

Classes
-------
QBaslerCamera
    Camera backed by a Basler device via the pylon GenTL producer.
QBaslerTree
    Parameter tree widget for :class:`QBaslerCamera` controls.
'''
from ._camera import QBaslerCamera
from ._tree import QBaslerTree
from QVideo.cameras._deprecated import deprecated_sources

#: The retired ``Q<Name>Source`` classes, until the next major release.
__getattr__ = deprecated_sources(__name__, QBaslerSource=QBaslerCamera)

__all__ = 'QBaslerCamera QBaslerTree'.split()
