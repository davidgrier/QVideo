from QVideo.cameras.Genicam.QGenicamCamera import QGenicamCamera, QGenicamSource
import logging

logger = logging.getLogger(__name__)

__all__ = ['QVimbaXCamera', 'QVimbaXSource']


class QVimbaXCamera(QGenicamCamera):

    '''Camera backed by an Allied Vision device via the VimbaX GenTL producer.

    `VimbaX <https://www.alliedvision.com/en/products/software/vimba-x-sdk/>`_
    is Allied Vision's SDK for GigE Vision and USB3 Vision cameras.  It
    installs a GenTL producer whose path is discovered automatically from the
    ``GENICAM_GENTL64_PATH`` environment variable set by the VimbaX installer.

    If VimbaX is not installed, instantiation raises :exc:`TypeError`.

    Parameters
    ----------
    cameraID : int
        Index of the Allied Vision camera to open.  Default: ``0``.
    '''

    producer = QGenicamCamera._findProducer(
        'VimbaUSBTL.cti', 'VimbaGigETL.cti', 'VimbaCL.cti')


class QVimbaXSource(QGenicamSource):

    '''Threaded video source backed by :class:`QVimbaXCamera`.

    Parameters
    ----------
    camera : QVimbaXCamera or None
        Camera instance to wrap.  If ``None``, a new
        :class:`QVimbaXCamera` is created from ``cameraID``.
    cameraID : int
        Index of the camera to open.  Used only when *camera* is ``None``.
        Default: ``0``.
    '''

    def __init__(self, camera: QVimbaXCamera | None = None,
                 cameraID: int = 0) -> None:
        camera = camera or QVimbaXCamera(cameraID=cameraID)
        super().__init__(camera)


if __name__ == '__main__':  # pragma: no cover
    QVimbaXCamera.example()
