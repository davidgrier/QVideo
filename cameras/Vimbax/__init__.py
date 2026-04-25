'''Allied Vision camera backend via the VimbaX GenTL producer.

Supports Allied Vision GigE Vision and USB3 Vision cameras through
`VimbaX <https://www.alliedvision.com/en/products/software/vimba-x-sdk/>`_,
Allied Vision's machine-vision SDK.  The VimbaX installer registers
GenTL producer paths in ``GENICAM_GENTL64_PATH``.

Classes
-------
QVimbaXCamera
    Camera backed by an Allied Vision device via the VimbaX GenTL producer.
QVimbaXSource
    Threaded video source backed by :class:`QVimbaXCamera`.
QVimbaXTree
    Parameter tree widget for :class:`QVimbaXCamera` controls.
'''
from ._camera import QVimbaXCamera, QVimbaXSource
from ._tree import QVimbaXTree


__all__ = 'QVimbaXCamera QVimbaXSource QVimbaXTree'.split()
