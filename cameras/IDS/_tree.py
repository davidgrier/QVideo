'''Camera property tree for IDS Imaging cameras.'''
from QVideo.cameras.Genicam import QGenicamTree
from QVideo.cameras.IDS import QIDSCamera
from typing import ClassVar


__all__ = ['QIDSTree']


class QIDSTree(QGenicamTree):

    '''Camera property tree for :class:`~QVideo.cameras.IDS.QIDSCamera`.

    Shows the standard controls of a GenICam camera and starts the camera
    in a known state.  See :class:`~QVideo.cameras.Genicam.QGenicamTree`
    for the parameters.
    '''

    _cameraClass = QIDSCamera
    _DEFAULT_CONTROLS = QGenicamTree.STANDARD_CONTROLS
    _DEFAULT_SETTINGS: ClassVar[dict[str, object]] = dict(
        QGenicamTree._DEFAULT_SETTINGS,
        AcquisitionFrameRateEnable=True,
        ExposureAuto='Off',
        GainAuto='Off',
    )


if __name__ == '__main__':  # pragma: no cover
    QIDSTree.example()
