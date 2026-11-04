'''Camera property tree for MATRIX VISION cameras.'''
from QVideo.cameras.Genicam import QGenicamTree
from QVideo.cameras.MV import QMVCamera
from typing import ClassVar


__all__ = ['QMVTree']


class QMVTree(QGenicamTree):

    '''Camera property tree for :class:`~QVideo.cameras.MV.QMVCamera`.

    Shows the standard controls of a GenICam camera and starts the camera
    in a known state.  See :class:`~QVideo.cameras.Genicam.QGenicamTree`
    for the parameters.
    '''

    _cameraClass = QMVCamera
    _DEFAULT_CONTROLS = QGenicamTree.STANDARD_CONTROLS
    _DEFAULT_SETTINGS: ClassVar[dict[str, object]] = dict(
        ExposureAuto='Off',
        GainAuto='Off',
    )


if __name__ == '__main__':  # pragma: no cover
    QMVTree.example()
