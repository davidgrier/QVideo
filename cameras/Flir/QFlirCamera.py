from QVideo.cameras.Genicam import QGenicamCamera
from pathlib import Path
import platform


class QFlirCamera(QGenicamCamera):

    def __init__(self, *args,
                 producer: str | None = None,
                 **kwargs) -> None:
        producer = producer or self.producer()
        print(producer)
        super().__init__(producer, *args, **kwargs)

    def producer(self) -> str:
        path = Path(__file__).parent
        os = platform.system()
        pythonversion = '.'.join(platform.python_version_tuple()[0:2])
        return str(path / os / pythonversion / 'Spinnaker_GenTL.cti')


if __name__ == '__main__':
    QFlirCamera.example()
