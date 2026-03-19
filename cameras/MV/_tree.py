from QVideo.cameras.Genicam import QGenicamTree
from QVideo.cameras.MV import QMVCamera
from QVideo.lib.QCameraTree import Source


__all__ = ['QMVTree']


class QMVTree(QGenicamTree):

    '''Camera property tree for :class:`~QVideo.cameras.MV.QMVCamera`.

    Builds a :class:`~QVideo.lib.QCameraTree.QCameraTree` using standard
    GenICam SFNC node names, suitable for any camera supported by the
    MATRIX VISION mvGenTLProducer.

    Parameters
    ----------
    camera : QMVCamera or None
        Camera instance to use.  If ``None``, a new :class:`QMVCamera`
        is created from ``cameraID``.
    cameraID : int
        Index of the camera to open.  Used only when *camera* is ``None``.
        Default: ``0``.
    controls : list of str or None
        Names of GenICam nodes to show.  Default: :attr:`_DEFAULT_CONTROLS`.
    '''

    _DEFAULT_CONTROLS = [
        'ReverseX',
        'ReverseY',
        'AcquisitionFrameRate',
        'AcquisitionResultingFrameRate',
        'ExposureTime',
        'ExposureAuto',
        'Gain',
        'GainAuto',
        'Gamma',
        'BlackLevel',
        'Width',
        'Height',
        'OffsetX',
        'OffsetY',
    ]

    _DEFAULT_SETTINGS = dict(
        ExposureAuto='Off',
        GainAuto='Off',
    )

    def __init__(self, *args,
                 camera: Source | None = None,
                 cameraID: int = 0,
                 controls: list[str] | None = None,
                 **kwargs) -> None:
        camera = camera or QMVCamera(cameraID=cameraID)
        camera.setSettings(self._DEFAULT_SETTINGS)
        super().__init__(*args,
                         camera=camera,
                         controls=controls or self._DEFAULT_CONTROLS,
                         **kwargs)


if __name__ == '__main__':  # pragma: no cover
    QMVTree.example()
