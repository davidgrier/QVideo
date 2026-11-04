'''IDS Imaging camera backend via the IDS peak GenTL producer.

Supports IDS USB3 Vision and GigE Vision cameras through
`IDS peak <https://www.ids-imaging.com/ids-peak.html>`_,
IDS Imaging's machine-vision SDK.  The IDS peak installer registers
GenTL producer paths in ``GENICAM_GENTL64_PATH``.

Classes
-------
QIDSCamera
    Camera backed by an IDS Imaging device via the IDS peak GenTL producer.
QIDSTree
    Parameter tree widget for :class:`QIDSCamera` controls.
'''
from ._camera import QIDSCamera
from ._tree import QIDSTree
from QVideo.cameras._deprecated import deprecated_sources

#: The retired ``Q<Name>Source`` classes, until the next major release.
__getattr__ = deprecated_sources(__name__, QIDSSource=QIDSCamera)

__all__ = 'QIDSCamera QIDSTree'.split()
