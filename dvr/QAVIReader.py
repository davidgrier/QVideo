from QVideo.lib import QReader
from PyQt5.QtCore import (pyqtProperty, pyqtSlot)
import cv2


class QAVIReader(QReader):
    '''Video reader for AVI files

    Reads frames from a video file,
    '''

    if cv2.__version__.startswith('2.'):
        SEEK = cv2.cv.CV_CAP_PROP_POS_FRAMES
        WIDTH = cv2.cv.CV_CAP_PROP_FRAME_WIDTH
        HEIGHT = cv2.cv.CV_CAP_PROP_FRAME_HEIGHT
        FRAMENUMBER = cv2.cv.CV_CAP_PROP_POS_FRAMES
        LENGTH = cv2.cv.CV_CAP_PROP_FRAME_COUNT
        FPS = cv2.cv.CV_CAP_PROP_FPS
        BRG2RGB = cv2.cv.CV_COLOR_BGR2RGB
    else:
        SEEK = cv2.CAP_PROP_POS_FRAMES
        WIDTH = cv2.CAP_PROP_FRAME_WIDTH
        HEIGHT = cv2.CAP_PROP_FRAME_HEIGHT
        FRAMENUMBER = cv2.CAP_PROP_POS_FRAMES
        LENGTH = cv2.CAP_PROP_FRAME_COUNT
        FPS = cv2.CAP_PROP_FPS
        BRG2RGB = cv2.COLOR_BGR2RGB

    def _initialize(self) -> bool:
        self.reader = cv2.VideoCapture(self.filename)
        return self.reader.isOpened()

    def _deinitialize(self) -> None:
        self.reader.release()
        self.reader = None

    def read(self) -> QReader.CameraData:
        ok, frame = self.reader.read()
        if ok and frame.ndim == 3:
            frame = cv2.cvtColor(frame, self.BRG2RGB)
        return ok, frame

    @pyqtSlot(int)
    def seek(self, framenumber: int) -> None:
        self.reader.set(self.SEEK, framenumber)

    @pyqtProperty(float)
    def fps(self) -> float:
        return self.reader.get(self.FPS)

    @pyqtProperty(int)
    def length(self) -> int:
        return int(self.reader.get(self.LENGTH))

    @pyqtProperty(int)
    def framenumber(self) -> int:
        return self.reader.get(self.FRAMENUMBER)

    @pyqtProperty(int)
    def width(self) -> int:
        return self.reader.get(self.WIDTH)

    @pyqtProperty(int)
    def height(self) -> int:
        return self.reader.get(self.HEIGHT)


def example() -> None:
    from pathlib import Path
    import QVideo

    path = Path(QVideo.__file__).parent / 'docs' / 'diatom3.avi'
    video = QAVIReader(str(path))
    print(str(path))
    print(f'{video.length = } frames')
    print(f'{video.width = } pixels')
    print(f'{video.height = } pixels')
    print(f'{video.fps = } fps')


if __name__ == '__main__':
    example()
