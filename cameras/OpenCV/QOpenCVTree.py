from QVideo.lib import QCameraTree
from QVideo.cameras.OpenCV import QOpenCVCamera


__all__ = ['QOpenCVTree']


class QOpenCVTree(QCameraTree):

    '''Camera tree for an :class:`~QVideo.cameras.OpenCV.QOpenCVCamera.QOpenCVCamera`.

    Convenience subclass of :class:`~QVideo.lib.QCameraTree.QCameraTree`
    that creates and opens a
    :class:`~QVideo.cameras.OpenCV.QOpenCVCamera.QOpenCVCamera` automatically
    if one is not provided.

    Parameters
    ----------
    camera : QOpenCVCamera or None
        Camera instance to use.  If ``None``, a new
        :class:`~QVideo.cameras.OpenCV.QOpenCVCamera.QOpenCVCamera` is
        created using *cameraID*.
    cameraID : int
        Index of the camera device to open.  Used only when *camera*
        is ``None``.  Default: ``0``.
    *args :
        Positional arguments forwarded to
        :class:`~QVideo.lib.QCameraTree.QCameraTree`.
    **kwargs :
        Keyword arguments forwarded to
        :class:`~QVideo.lib.QCameraTree.QCameraTree`.
    '''

    def __init__(self, *args,
                 camera: QOpenCVCamera | None = None,
                 cameraID: int = 0,
                 **kwargs) -> None:
        if camera is None:
            camera = QOpenCVCamera(cameraID=cameraID)
        super().__init__(camera, *args, **kwargs)


if __name__ == '__main__':  # pragma: no cover
    QOpenCVTree.example()
