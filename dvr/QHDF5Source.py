from QVideo.dvr.QHDF5Reader import QHDF5Reader
from QVideo.lib import QVideoSource
from typing import Union


class QHDF5Source(QVideoSource):

    def __init__(self, reader: Union[str, QHDF5Reader]) -> None:
        if isinstance(reader, str):
            reader = QHDF5Reader(reader)
        super().__init__(reader)
