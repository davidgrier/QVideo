'''OpenCV video reader.'''
from qtpy import QtCore
from QVideo.lib import QCamera, QVideoReader
import cv2
import numpy as np


__all__ = ['QOpenCVReader']


class QOpenCVReader(QVideoReader):

    '''Video reader for common video file formats (AVI, MKV, MP4, etc.).

    Reads frames from a video file using OpenCV's ``VideoCapture``.
    Frames are converted from BGR (OpenCV native) to RGB on read.  A file
    of 16-bit gray frames (written by :class:`QOpenCVWriter` or by PyAV)
    is read as 2-D ``uint16`` arrays, which needs OpenCV 4.7 or newer
    with FFmpeg.

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
        if self._isDeep():
            self._reader = cv2.VideoCapture(
                self.filename, cv2.CAP_FFMPEG,
                [cv2.CAP_PROP_CONVERT_RGB, 0])
        else:
            self._reader = cv2.VideoCapture(self.filename)
        if not self._reader.isOpened():
            return False
        self._framenumber = 0
        return True

    def _isDeep(self) -> bool:
        '''Return ``True`` if the file holds 16-bit gray frames.

        OpenCV converts every frame to 8-bit BGR unless it is told not to,
        so the first frame is read once without conversion to find out.
        '''
        probe = cv2.VideoCapture(
            self.filename, cv2.CAP_FFMPEG, [cv2.CAP_PROP_CONVERT_RGB, 0])
        try:
            ok, frame = probe.read()
        finally:
            probe.release()
        return bool(ok) and frame.ndim == 2 and frame.dtype == np.uint16

    def _deinitialize(self) -> None:
        if self._reader is not None:
            self._reader.release()
        self._reader = None

    def read(self) -> QCamera.CameraData:
        '''Read the next frame from the video file.

        Frames are converted from BGR (OpenCV native) to RGB on read.

        Returns
        -------
        tuple[bool, ndarray or None]
            ``(True, frame)`` on success, ``(False, None)`` at end-of-file
            or when the reader is not open.
        '''
        if not self.isOpen():
            return False, None
        ok, frame = self._reader.read()
        if not ok:
            return False, None
        if frame.ndim == 3:
            frame = cv2.cvtColor(frame, self._COLOR_BGR2RGB)
        self._framenumber += 1
        return True, frame

    @QtCore.Slot(int)
    def seek(self, framenumber: int) -> None:
        '''Seek to the specified frame number.'''
        self._reader.set(self.FRAMENUMBER, framenumber)
        self._framenumber = framenumber

    @property
    def fps(self) -> float:
        '''Frame rate reported by the video file [fps].

        :attr:`DEFAULT_FPS` if the file reports none (OpenCV answers 0).
        '''
        return self._reader.get(self.FPS) or self.DEFAULT_FPS

    @property
    def length(self) -> int:
        '''Total number of frames in the video file.'''
        return int(self._reader.get(self.LENGTH))

    @property
    def framenumber(self) -> int:
        '''Index of the next frame to be returned by :meth:`read`.'''
        return self._framenumber

    @property
    def width(self) -> int:
        '''Frame width in pixels.'''
        return int(self._reader.get(self.WIDTH))

    @property
    def height(self) -> int:
        '''Frame height in pixels.'''
        return int(self._reader.get(self.HEIGHT))
