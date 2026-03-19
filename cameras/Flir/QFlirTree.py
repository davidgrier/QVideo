from QVideo.cameras.Genicam import QGenicamTree
from QVideo.cameras.Flir.QFlirCamera import QFlirCamera
from QVideo.lib.QCameraTree import Source


__all__ = ['QFlirTree']


class QFlirTree(QGenicamTree):

    '''Camera property tree for :class:`~QVideo.cameras.Flir.QFlirCamera`.

    Builds a :class:`~QVideo.lib.QCameraTree.QCameraTree` with a curated
    set of controls and sensible default settings for FLIR cameras.

    Parameters
    ----------
    camera : QFlirCamera or None
        Camera instance to use.  If ``None``, a new :class:`QFlirCamera`
        is created from ``cameraID``.
    cameraID : int
        Index of the FLIR camera to open.  Used only when *camera* is
        ``None``.  Default: ``0``.
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
        AcquisitionFrameRateEnable=True,
        BlackLevelSelector='All',
        GammaEnable=True,
        AutoExposureControlPriority='Gain',
        ExposureAuto='Off',
        ExposureMode='Timed',
        ExposureTimeMode='Common',
        GainAuto='Off',
    )

    def __init__(self, *args,
                 camera: Source | None = None,
                 cameraID: int = 0,
                 controls: list[str] | None = None,
                 **kwargs) -> None:
        camera = camera or QFlirCamera(cameraID=cameraID)
        camera.setSettings(self._DEFAULT_SETTINGS)
        super().__init__(*args,
                         camera=camera,
                         controls=controls or self._DEFAULT_CONTROLS,
                         **kwargs)


if __name__ == '__main__':  # pragma: no cover
    QFlirTree.example()
