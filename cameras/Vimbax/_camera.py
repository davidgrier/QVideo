'''Allied Vision camera and threaded video source (VimbaX producer).'''
from QVideo.cameras.Genicam import QGenicamCamera
import logging

logger = logging.getLogger(__name__)

__all__ = ['QVimbaXCamera']


class QVimbaXCamera(QGenicamCamera):

    '''Camera backed by an Allied Vision device via the VimbaX GenTL producer.

    `VimbaX <https://www.alliedvision.com/en/products/software/vimba-x-sdk/>`_
    is Allied Vision's SDK for GigE Vision and USB3 Vision cameras.  It
    installs a GenTL producer whose path is discovered automatically from the
    ``GENICAM_GENTL64_PATH`` environment variable set by the VimbaX installer.

    If VimbaX is not installed, or the producer or camera cannot be
    found, instantiation raises :exc:`~QVideo.lib.errors.QCameraError`
    with a message describing what is missing.  Run
    ``python -m QVideo.cameras.gentl VimbaUSBTL.cti`` for a step-by-step
    diagnosis.

    Parameters
    ----------
    cameraID : int
        Index of the Allied Vision camera to open.  Default: ``0``.
    '''

    _producerFilenames = ('VimbaUSBTL.cti', 'VimbaGigETL.cti', 'VimbaCL.cti')
    _producerHint = ('Install VimbaX and set GENICAM_GENTL64_PATH to the '
                     'directory containing VimbaUSBTL.cti.')


if __name__ == '__main__':  # pragma: no cover
    QVimbaXCamera.example()
