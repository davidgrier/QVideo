from QVideo.cameras.Genicam import QGenicamTree
from QVideo.cameras.Flir.QFlirCamera import QFlirCamera
from genicam.genapi import EVisibility


class QFlirTree(QGenicamTree):

    def __init__(self, *args,
                 camera: QGenicamTree.Source | None = None,
                 cameraID: int = 0,
                 controls: list[str] | None = None,
                 **kwargs) -> None:
        camera = camera or QFlirCamera(cameraID=cameraID)
        camera.setSettings(self._defaultSettings())
        controls = self._defaultControls()
        super().__init__(camera=camera,
                         controls=controls,
                         visibility=EVisibility.Guru,
                         *args, **kwargs)

    def _defaultControls(self) -> list[str]:
        return ['ReverseX',
                'ReverseY',
                'AcquisitionFrameRate',
                'AcquisitionResultingFrameRate',
                'ExposureTime',
                'ExposureAuto',
                'Gain',
                'GainAuto',
                'Gamma',
                'Width',
                'Height',
                'OffsetX',
                'OffsetY']

    def _defaultSettings(self) -> QFlirCamera.Settings:
        return dict(AcquisitionFrameRateEnable=True,
                    BlackLevelSelector='All',
                    GammaEnable=True,
                    AutoExpsureControlPriority='Gain',
                    ExposureAuto='Off',
                    ExposureMode='Timed',
                    ExposureTimeMode='Common',
                    GainAuto='Off')


if __name__ == '__main__':
    QFlirTree.example()
