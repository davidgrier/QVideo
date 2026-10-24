from QVideo.lib import QCameraTree
from QVideo.cameras.OpenCV import QOpenCVCamera


__all__ = ['QOpenCVTree']


class QOpenCVTree(QCameraTree):

    '''Camera control tree for :class:`~QVideo.cameras.OpenCV.QOpenCVCamera`.

    The camera's ``resolution`` property, whose allowed values are the
    formats probed from the device, appears as a dropdown.  Selecting an
    entry atomically updates width, height, and frame rate on the live
    device without stopping the video source.

    Width, height, and fps are displayed as read-only fields.  All format
    changes go through the ``resolution`` dropdown.

    When no format information is available (e.g. when
    :class:`~QtMultimedia.QMediaDevices` is absent and probing fails),
    the dropdown is omitted and the tree falls back to the standard
    read-only width/height display.

    Parameters
    ----------
    camera : QOpenCVCamera or None
        Camera instance to use.  If ``None``, a new
        :class:`~QVideo.cameras.OpenCV.QOpenCVCamera` is created from the
        keyword arguments below.
    cameraID : int
        Index of the camera device to open.  Used only when *camera* is
        ``None``.  Default: ``0``.
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
        # fps is controlled by the resolution dropdown when formats are known
        if 'resolution' in self._parameters and 'fps' in self._parameters:
            self._parameters['fps'].setOpts(enabled=False)


if __name__ == '__main__':  # pragma: no cover
    QOpenCVTree.example()
