from QVideo.cameras.Genicam import QGenicamCamera
from pathlib import Path
import platform
import logging


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class QFlirCamera(QGenicamCamera):

    def __init__(self, *args,
                 producer: str | None = None,
                 **kwargs) -> None:
        producer = producer or self.producer()
        super().__init__(producer, *args, **kwargs)

    def producer(self) -> str:
        pname = 'Spinnaker_GenTL.cti'
        root = Path(__file__).parent
        os = platform.system()
        pythonversion = '.'.join(platform.python_version_tuple()[0:2])
        path = root / 'producer' / os / pythonversion / pname
        if not path.exists():
            logger.warning(f'{pname} not available '
                           f'for python {pythonversion} on {os}')
            return ''
        return str(path)


if __name__ == '__main__':
    QFlirCamera.example()
