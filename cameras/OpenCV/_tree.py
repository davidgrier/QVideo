from QVideo.lib import QCameraTree
from QVideo.cameras.OpenCV import QOpenCVCamera


__all__ = ['QOpenCVTree']


class QOpenCVTree(QCameraTree):

    '''Camera tree for :class:`~QVideo.cameras.OpenCV.QOpenCVCamera.QOpenCVCamera`.

    Convenience subclass of :class:`~QVideo.lib.QCameraTree.QCameraTree`
    that automatically creates and opens a
    :class:`~QVideo.cameras.OpenCV.QOpenCVCamera.QOpenCVCamera`
    if one is not provided.  Width and height are disabled in the
    parameter tree — they are writable via
    :meth:`~QVideo.lib.QCamera.QCamera.set` (used by
    :class:`~QVideo.lib.QResolutionControl.QResolutionControl`) but
    must not be changed without stopping the video source first.

    Parameters
    ----------
    camera : QOpenCVCamera or None
        Camera instance to use.  If ``None``, a new
        :class:`~QVideo.cameras.OpenCV.QOpenCVCamera.QOpenCVCamera` is
        created from the camera keyword arguments below.
    cameraID : int
        Index of the camera device to open.  Used only when *camera*
        is ``None``.  Default: ``0``.
    mirrored : bool
        Flip the image horizontally.  Used only when *camera* is ``None``.
        Default: ``False``.
    flipped : bool
        Flip the image vertically.  Used only when *camera* is ``None``.
        Default: ``False``.
    gray : bool
        Open in grayscale mode.  Used only when *camera* is ``None``.
        Default: ``False``.
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
                 mirrored: bool = False,
                 flipped: bool = False,
                 gray: bool = False,
                 **kwargs) -> None:
        if camera is None:
            camera = QOpenCVCamera(cameraID=cameraID,
                                   mirrored=mirrored,
                                   flipped=flipped,
                                   gray=gray)
        super().__init__(camera, *args, **kwargs)
        for key in ('width', 'height'):
            if key in self._parameters:
                self._parameters[key].setOpts(enabled=False)


if __name__ == '__main__':  # pragma: no cover
    QOpenCVTree.example()
