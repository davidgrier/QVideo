'''IDS Imaging camera and threaded video source (IDS peak producer).'''
from QVideo.cameras.Genicam import QGenicamCamera, QGenicamSource


__all__ = ['QIDSCamera', 'QIDSSource']


class QIDSCamera(QGenicamCamera):

    '''Camera backed by an IDS Imaging device via the IDS peak GenTL producer.

    `IDS peak <https://www.ids-imaging.com/ids-peak.html>`_ is IDS Imaging's
    SDK for USB3 Vision and GigE Vision cameras.  It installs GenTL producers
    whose paths are discovered automatically from the ``GENICAM_GENTL64_PATH``
    environment variable set by the IDS peak installer.

    If IDS peak is not installed, or the producer or camera cannot be
    found, instantiation raises :exc:`~QVideo.lib.errors.QCameraError`
    with a message describing what is missing.  Run
    ``python -m QVideo.lib.gentl ids_u3vgentl.cti`` for a
    step-by-step diagnosis.

    Parameters
    ----------
    cameraID : int
        Index of the IDS camera to open.  Default: ``0``.
    '''

    _producer_filenames = ('ids_u3vgentl.cti', 'ids_gevgentl.cti')
    _producerHint = (
        'Install IDS peak and set GENICAM_GENTL64_PATH to the '
        'directory containing ids_u3vgentl.cti or ids_gevgentl.cti.')


class QIDSSource(QGenicamSource):

    '''Threaded video source backed by :class:`QIDSCamera`.

    Parameters
    ----------
    camera : QIDSCamera or None
        Camera instance to wrap.  If ``None``, a new
        :class:`QIDSCamera` is created from ``cameraID``.
    cameraID : int
        Index of the camera to open.  Used only when *camera* is ``None``.
        Default: ``0``.
    '''

    def __init__(self, camera: QIDSCamera | None = None,
                 cameraID: int = 0) -> None:
        camera = camera or QIDSCamera(cameraID=cameraID)
        super().__init__(camera)


if __name__ == '__main__':  # pragma: no cover
    QIDSCamera.example()
