'''Camera property tree for FLIR cameras.'''
from QVideo.cameras.Genicam import QGenicamTree
from QVideo.cameras.Flir import QFlirCamera
from typing import ClassVar


__all__ = ['QFlirTree']


class QFlirTree(QGenicamTree):

    '''Camera property tree for :class:`~QVideo.cameras.Flir.QFlirCamera`.

    Shows the standard controls of a GenICam camera and starts the camera
    in a known state.  See :class:`~QVideo.cameras.Genicam.QGenicamTree`
    for the parameters.
    '''

    _cameraClass = QFlirCamera
    _DEFAULT_CONTROLS = QGenicamTree.STANDARD_CONTROLS
    _DEFAULT_SETTINGS: ClassVar[dict[str, object]] = dict(
        AcquisitionFrameRateEnable=True,
        BlackLevelSelector='All',
        GammaEnable=True,
        AutoExposureControlPriority='Gain',
        AutoAlgorithmSelector='Ae',
        AutoExposureTargetGreyValueAuto='Off',
        ExposureAuto='Off',
        ExposureMode='Timed',
        ExposureTimeMode='Common',
        GainAuto='Off',
    )


if __name__ == '__main__':  # pragma: no cover
    QFlirTree.example()
