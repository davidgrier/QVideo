'''Camera property tree for Basler cameras.'''
from QVideo.cameras.Genicam import QGenicamTree
from QVideo.cameras.Basler import QBaslerCamera
from typing import ClassVar


__all__ = ['QBaslerTree']


class QBaslerTree(QGenicamTree):

    '''Camera property tree for :class:`~QVideo.cameras.Basler.QBaslerCamera`.

    Shows the standard controls of a GenICam camera and starts the camera
    in a known state.  See :class:`~QVideo.cameras.Genicam.QGenicamTree`
    for the parameters.
    '''

    _cameraClass = QBaslerCamera
    _DEFAULT_CONTROLS = QGenicamTree.STANDARD_CONTROLS
    _DEFAULT_SETTINGS: ClassVar[dict[str, object]] = dict(
        AcquisitionFrameRateEnable=True,
        BlackLevelSelector='All',
        GammaEnable=True,
        ExposureAuto='Off',
        GainAuto='Off',
    )


if __name__ == '__main__':  # pragma: no cover
    QBaslerTree.example()
