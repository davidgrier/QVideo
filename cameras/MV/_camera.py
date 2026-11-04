'''MATRIX VISION camera and threaded video source (mvGenTLProducer).'''
from QVideo.cameras.Genicam import QGenicamCamera


__all__ = ['QMVCamera']


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

    If mvIMPACT SDK is not installed, or the producer or camera cannot be
    found, instantiation raises :exc:`~QVideo.lib.errors.QCameraError`
    with a message describing what is missing.  Run
    ``python -m QVideo.cameras.gentl mvGenTLProducer.cti`` for a
    step-by-step diagnosis.

    Parameters
    ----------
    cameraID : int
        Index of the camera to open.  Default: ``0``.
    '''

    _producerFilenames = ('mvGenTLProducer.cti',)
    _producerHint = (
        'Install the mvIMPACT SDK and set GENICAM_GENTL64_PATH to the '
        'directory containing mvGenTLProducer.cti.')


if __name__ == '__main__':  # pragma: no cover
    QMVCamera.example()
