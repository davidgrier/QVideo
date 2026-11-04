'''Basler camera and threaded video source (pylon GenTL producer).'''
from QVideo.cameras.Genicam import QGenicamCamera


__all__ = ['QBaslerCamera']


class QBaslerCamera(QGenicamCamera):

    '''Camera backed by a Basler device via the pylon GenTL producer.

    `pylon <https://www.baslerweb.com/en/software/pylon/>`_ is Basler's
    SDK for machine-vision cameras.  It installs separate GenTL producers
    for USB3 Vision and GigE Vision cameras whose paths are discovered
    automatically from the ``GENICAM_GENTL64_PATH`` environment variable
    set by the pylon installer.

    If pylon is not installed, or the producer or camera cannot be
    found, instantiation raises :exc:`~QVideo.lib.errors.QCameraError`
    with a message describing what is missing.  Run
    ``python -m QVideo.cameras.gentl ProducerU3V.cti`` for a
    step-by-step diagnosis.

    Parameters
    ----------
    cameraID : int
        Index of the Basler camera to open.  Default: ``0``.
    '''

    _producerFilenames = ('ProducerU3V.cti', 'ProducerGEV.cti')
    _producerHint = (
        'Install pylon and set GENICAM_GENTL64_PATH to the '
        'directory containing ProducerU3V.cti or ProducerGEV.cti.')


if __name__ == '__main__':  # pragma: no cover
    QBaslerCamera.example()
