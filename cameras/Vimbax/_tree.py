from QVideo.cameras.Genicam import QGenicamTree
from QVideo.cameras.Vimbax import QVimbaXCamera
from QVideo.lib.QCameraTree import Source

import logging

logger = logging.getLogger(__name__)

__all__ = ['QVimbaXTree']


class QVimbaXTree(QGenicamTree):

    '''Camera property tree for Allied Vision VimbaX cameras.

    Parameters
    ----------
    camera : QVimbaXCamera or None
        Camera instance to use.  If ``None``, a new
        :class:`QVimbaXCamera` is created from ``cameraID``.
    cameraID : int
        Index of the camera device to open.  Used only when *camera* is
        ``None``.  Default: ``0``.
    *args, **kwargs :
        Forwarded to :class:`~QVideo.cameras.Genicam.QGenicamTree`.
    '''

    def __init__(self, *args,
                 camera: Source | None = None,
                 cameraID: int = 0,
                 **kwargs) -> None:
        camera = camera or QVimbaXCamera(cameraID=cameraID)
        super().__init__(*args, camera=camera, **kwargs)


if __name__ == '__main__':  # pragma: no cover
    QVimbaXTree.example()
