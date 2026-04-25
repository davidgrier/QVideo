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
QBaslerSource
    Threaded video source backed by :class:`QBaslerCamera`.
QBaslerTree
    Parameter tree widget for :class:`QBaslerCamera` controls.
'''
from ._camera import QBaslerCamera, QBaslerSource
from ._tree import QBaslerTree


__all__ = 'QBaslerCamera QBaslerSource QBaslerTree'.split()
