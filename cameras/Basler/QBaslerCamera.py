from QVideo.cameras.Genicam import QGenicamCamera, QGenicamSource


__all__ = ['QBaslerCamera', 'QBaslerSource']


class QBaslerCamera(QGenicamCamera):

    '''Camera backed by a Basler device via the pylon GenTL producer.

    `pylon <https://www.baslerweb.com/en/software/pylon/>`_ is Basler's
    SDK for machine-vision cameras.  It installs separate GenTL producers
    for USB3 Vision and GigE Vision cameras whose paths are discovered
    automatically from the ``GENICAM_GENTL64_PATH`` environment variable
    set by the pylon installer.

    If pylon is not installed, instantiation raises :exc:`TypeError`.

    Parameters
    ----------
    cameraID : int
        Index of the Basler camera to open.  Default: ``0``.
    '''

    producer = QGenicamCamera._findProducer('ProducerU3V.cti',
                                            'ProducerGEV.cti')


class QBaslerSource(QGenicamSource):

    '''Threaded video source backed by :class:`QBaslerCamera`.

    Parameters
    ----------
    camera : QBaslerCamera or None
        Camera instance to wrap.  If ``None``, a new
        :class:`QBaslerCamera` is created from ``cameraID``.
    cameraID : int
        Index of the camera to open.  Used only when *camera* is ``None``.
        Default: ``0``.
    '''

    def __init__(self, camera: QBaslerCamera | None = None,
                 cameraID: int = 0) -> None:
        camera = camera or QBaslerCamera(cameraID=cameraID)
        super().__init__(camera)


if __name__ == '__main__':  # pragma: no cover
    QBaslerCamera.example()
