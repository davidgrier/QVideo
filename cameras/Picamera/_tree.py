from QVideo.lib import QCameraTree
from QVideo.cameras.Picamera import QPicamera


__all__ = ['QPicameraTree']


class QPicameraTree(QCameraTree):

    '''Camera control tree for :class:`~QVideo.cameras.Picamera.QPicamera`.

    Convenience subclass of :class:`~QVideo.lib.QCameraTree.QCameraTree`
    that automatically creates and opens a :class:`QPicamera` if one is
    not provided.

    Parameters
    ----------
    camera : QPicamera or None
        Camera instance to use.  If ``None``, a new :class:`QPicamera`
        is created from the keyword arguments below.
    cameraID : int
        Camera index.  Used only when *camera* is ``None``.  Default: ``0``.
    width : int
        Initial frame width.  Used only when *camera* is ``None``.
        Default: ``1280``.
    height : int
        Initial frame height.  Used only when *camera* is ``None``.
        Default: ``960``.
    *args :
        Forwarded to :class:`~QVideo.lib.QCameraTree.QCameraTree`.
    **kwargs :
        Forwarded to :class:`~QVideo.lib.QCameraTree.QCameraTree`.
    '''

    def __init__(self, *args,
                 camera: QPicamera | None = None,
                 cameraID: int = 0,
                 width: int = 1280,
                 height: int = 960,
                 **kwargs) -> None:
        if camera is None:
            camera = QPicamera(cameraID=cameraID, width=width, height=height)
        super().__init__(camera, *args, **kwargs)


if __name__ == '__main__':  # pragma: no cover
    QPicameraTree.example()
