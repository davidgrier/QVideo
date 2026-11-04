'''IDS Imaging camera and threaded video source (IDS peak producer).'''
from QVideo.cameras.Genicam import QGenicamCamera


__all__ = ['QIDSCamera']


class QIDSCamera(QGenicamCamera):

    '''Camera backed by an IDS Imaging device via the IDS peak GenTL producer.

    `IDS peak <https://www.ids-imaging.com/ids-peak.html>`_ is IDS Imaging's
    SDK for USB3 Vision and GigE Vision cameras.  It installs GenTL producers
    whose paths are discovered automatically from the ``GENICAM_GENTL64_PATH``
    environment variable set by the IDS peak installer.

    If IDS peak is not installed, or the producer or camera cannot be
    found, instantiation raises :exc:`~QVideo.lib.errors.QCameraError`
    with a message describing what is missing.  Run
    ``python -m QVideo.cameras.gentl ids_u3vgentl.cti`` for a
    step-by-step diagnosis.

    Parameters
    ----------
    cameraID : int
        Index of the IDS camera to open.  Default: ``0``.
    '''

    _producerFilenames = ('ids_u3vgentl.cti', 'ids_gevgentl.cti')
    _producerHint = (
        'Install IDS peak and set GENICAM_GENTL64_PATH to the '
        'directory containing ids_u3vgentl.cti or ids_gevgentl.cti.')


if __name__ == '__main__':  # pragma: no cover
    QIDSCamera.example()
