from QVideo.cameras.Genicam import QGenicamCamera, QGenicamSource


__all__ = ['QFlirCamera', 'QFlirSource']


class QFlirCamera(QGenicamCamera):

    '''Camera backed by a FLIR device via the Spinnaker GenTL producer.

    `Spinnaker <https://www.flir.com/products/spinnaker-sdk/>`_ is FLIR's
    SDK for machine-vision cameras.  It installs a GenTL producer whose
    path is discovered automatically from the ``GENICAM_GENTL64_PATH``
    environment variable set by the Spinnaker installer.

    If Spinnaker is not installed, instantiation raises :exc:`TypeError`.

    .. warning::

        Spinnaker GenTL producer **4.3.0.189** contains a bug in which
        ``DevClose()`` hangs indefinitely when the camera is released.
        This causes the application to hang on exit.  FLIR customer
        support has confirmed the bug.  If you experience this issue,
        downgrade to Spinnaker **4.1.0.172** or earlier.

    Parameters
    ----------
    cameraID : int
        Index of the FLIR camera to open.  Default: ``0``.
    '''

    producer = QGenicamCamera._findProducer('Spinnaker_GenTL.cti')


class QFlirSource(QGenicamSource):

    '''Threaded video source backed by :class:`QFlirCamera`.

    Parameters
    ----------
    camera : QFlirCamera or None
        Camera instance to wrap.  If ``None``, a new
        :class:`QFlirCamera` is created from ``cameraID``.
    cameraID : int
        Index of the camera to open.  Used only when *camera* is ``None``.
        Default: ``0``.
    '''

    def __init__(self, camera: QFlirCamera | None = None,
                 cameraID: int = 0) -> None:
        camera = camera or QFlirCamera(cameraID=cameraID)
        super().__init__(camera)


if __name__ == '__main__':  # pragma: no cover
    QFlirCamera.example()
