'''IDS Imaging camera backend via the IDS peak GenTL producer.

Supports IDS USB3 Vision and GigE Vision cameras through
`IDS peak <https://www.ids-imaging.com/ids-peak.html>`_,
IDS Imaging's machine-vision SDK.  The IDS peak installer registers
GenTL producer paths in ``GENICAM_GENTL64_PATH``.

Classes
-------
QIDSCamera
    Camera backed by an IDS Imaging device via the IDS peak GenTL producer.
QIDSSource
    Threaded video source backed by :class:`QIDSCamera`.
QIDSTree
    Parameter tree widget for :class:`QIDSCamera` controls.
'''
from ._camera import QIDSCamera, QIDSSource
from ._tree import QIDSTree


__all__ = 'QIDSCamera QIDSSource QIDSTree'.split()
