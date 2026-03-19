from QVideo.cameras.Genicam import QGenicamCamera, QGenicamSource


__all__ = ['QMVCamera', 'QMVSource']


class QMVCamera(QGenicamCamera):

    '''Camera backed by any GenICam-compliant device via the MATRIX VISION
    mvGenTLProducer universal GenTL producer.

    `mvGenTLProducer
    <https://www.matrix-vision.com/software-support.html>`_
    is a free universal GenTL producer from MATRIX VISION that supports a
    broad range of GenICam-compliant cameras from many manufacturers.
    Installing the mvIMPACT SDK registers the producer path in
    ``GENICAM_GENTL64_PATH`` automatically.

    .. note::
        FLIR/Spinnaker cameras are not supported by this backend; use
        :class:`~QVideo.cameras.Flir.QFlirCamera` instead.

    If mvIMPACT SDK is not installed, instantiation raises :exc:`TypeError`.

    Parameters
    ----------
    cameraID : int
        Index of the camera to open.  Default: ``0``.
    '''

    producer = QGenicamCamera._findProducer('mvGenTLProducer.cti')


class QMVSource(QGenicamSource):

    '''Threaded video source backed by :class:`QMVCamera`.

    Parameters
    ----------
    camera : QMVCamera or None
        Camera instance to wrap.  If ``None``, a new
        :class:`QMVCamera` is created from ``cameraID``.
    cameraID : int
        Index of the camera to open.  Used only when *camera* is ``None``.
        Default: ``0``.
    '''

    def __init__(self, camera: QMVCamera | None = None,
                 cameraID: int = 0) -> None:
        camera = camera or QMVCamera(cameraID=cameraID)
        super().__init__(camera)


if __name__ == '__main__':  # pragma: no cover
    QMVCamera.example()
