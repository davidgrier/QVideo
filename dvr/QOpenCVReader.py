from qtpy import QtCore
from QVideo.lib import QVideoReader, QVideoSource
from pathlib import Path
import cv2


__all__ = ['QOpenCVReader', 'QOpenCVSource']


class QOpenCVReader(QVideoReader):

    '''Video reader for common video file formats (AVI, MKV, MP4, etc.).

    Reads frames from a video file using OpenCV's ``VideoCapture``.
    Frames are converted from BGR (OpenCV native) to RGB on read.

    Parameters
    ----------
    filename : str
        Path to the video file to read.
    '''

    FRAMENUMBER = cv2.CAP_PROP_POS_FRAMES
    WIDTH = cv2.CAP_PROP_FRAME_WIDTH
    HEIGHT = cv2.CAP_PROP_FRAME_HEIGHT
    LENGTH = cv2.CAP_PROP_FRAME_COUNT
    FPS = cv2.CAP_PROP_FPS
    _COLOR_BGR2RGB = cv2.COLOR_BGR2RGB

    def _initialize(self) -> bool:
        self.reader = cv2.VideoCapture(self.filename)
        if not self.reader.isOpened():
            return False
        self._framenumber = 0
        return True

    def _deinitialize(self) -> None:
        if self.reader is not None:
            self.reader.release()
        self.reader = None

    def read(self) -> QVideoReader.CameraData:
        if not self.isOpen():
            return False, None
        ok, frame = self.reader.read()
        if not ok:
            return False, None
        if frame.ndim == 3:
            frame = cv2.cvtColor(frame, self._COLOR_BGR2RGB)
        self._framenumber += 1
        return True, frame

    @QtCore.Slot(int)
    def seek(self, framenumber: int) -> None:
        '''Seek to the specified frame number.'''
        self.reader.set(self.FRAMENUMBER, framenumber)
        self._framenumber = framenumber

    @QtCore.Property(float)
    def fps(self) -> float:
        return self.reader.get(self.FPS)

    @QtCore.Property(int)
    def length(self) -> int:
        return int(self.reader.get(self.LENGTH))

    @QtCore.Property(int)
    def framenumber(self) -> int:
        return self._framenumber

    @QtCore.Property(int)
    def width(self) -> int:
        return int(self.reader.get(self.WIDTH))

    @QtCore.Property(int)
    def height(self) -> int:
        return int(self.reader.get(self.HEIGHT))


class QOpenCVSource(QVideoSource):

    '''Video source for common video file formats (AVI, MKV, MP4, etc.).

    Parameters
    ----------
    reader : str, Path, or QOpenCVReader
        Path to the video file to read, or an existing
        :class:`QOpenCVReader` instance.
    '''

    def __init__(self, reader: str | Path | QOpenCVReader) -> None:
        if isinstance(reader, (str, Path)):
            reader = QOpenCVReader(str(reader))
        super().__init__(reader)


if __name__ == '__main__':  # pragma: no cover
    QOpenCVReader.example()
