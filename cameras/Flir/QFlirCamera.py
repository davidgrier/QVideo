from QVideo.cameras.Genicam import QGenicamCamera
from pathlib import Path


class QFlirCamera(QGenicamCamera):

    def __init__(self, *args, **kwargs) -> None:
        path = Path(__file__).parent
        producer = str(path / 'Spinnaker_GenTL.cti')
        super().__init__(producer, *args, **kwargs)
        self.setup()

    def setup(self) -> None:
        self.set('AcquisitionFrameRateEnable', True)
        self.set('GammaEnable', True)
        self.set('Gamma', 1.)


if __name__ == '__main__':
    QFlirCamera.example()
