'''Allied Vision camera backend via the VimbaX GenTL producer.

Supports Allied Vision GigE Vision and USB3 Vision cameras through
`VimbaX <https://www.alliedvision.com/en/products/software/vimba-x-sdk/>`_,
Allied Vision's machine-vision SDK.  The VimbaX installer registers
GenTL producer paths in ``GENICAM_GENTL64_PATH``.

Classes
-------
QVimbaXCamera
    Camera backed by an Allied Vision device via the VimbaX GenTL producer.
QVimbaXTree
    Parameter tree widget for :class:`QVimbaXCamera` controls.
'''
from ._camera import QVimbaXCamera
from ._tree import QVimbaXTree
from QVideo.cameras._deprecated import deprecated_sources

#: The retired ``Q<Name>Source`` classes, until the next major release.
__getattr__ = deprecated_sources(__name__, QVimbaXSource=QVimbaXCamera)

__all__ = 'QVimbaXCamera QVimbaXTree'.split()
