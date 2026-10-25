from QVideo.cameras.Genicam import QGenicamCamera, QGenicamSource


__all__ = ['QFlirCamera', 'QFlirSource']


class QFlirCamera(QGenicamCamera):

    '''Camera backed by a FLIR device via the Spinnaker GenTL producer.

    `Spinnaker <https://www.flir.com/products/spinnaker-sdk/>`_ is FLIR's
    SDK for machine-vision cameras.  It installs a GenTL producer whose
    path is discovered automatically from the ``GENICAM_GENTL64_PATH``
    environment variable set by the Spinnaker installer.

    If the packages, the producer or the camera cannot be found,
    instantiation raises :exc:`~QVideo.lib.errors.QCameraError` with a
    message describing what is missing.  Run
    ``python -m QVideo.lib.gentl Spinnaker_GenTL.cti`` for a step-by-step
    diagnosis.

    .. note::

        Spinnaker GenTL producer 4.3.0.189 hangs in ``DevClose()`` when
        the camera is released, which blocks application exit.  The bug
        is fixed in Spinnaker 4.4.0.

    Parameters
    ----------
    cameraID : int
        Index of the FLIR camera to open.  Default: ``0``.
    '''

    _producer_filenames = ('Spinnaker_GenTL.cti',)
    _producerHint = ('Install the Spinnaker SDK and set GENICAM_GENTL64_PATH '
                     'to the directory containing Spinnaker_GenTL.cti '
                     '(on Linux, typically /opt/spinnaker/lib/spinnaker-gentl).')


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
