'''PyAV video reader and threaded playback source.'''
from qtpy import QtCore
from QVideo.lib import QCamera, QVideoReader, QVideoSource
from pathlib import Path


__all__ = ['QPyAVReader', 'QPyAVSource']


class QPyAVReader(QVideoReader):

    '''Video reader that uses PyAV, the Python binding of FFmpeg.

    Reads the frames of any video file that FFmpeg can decode, and
    returns 8-bit and 16-bit gray frames as such and everything else as
    8-bit RGB.  Seeking is exact for the codecs that store every frame
    whole, such as FFV1; for the others the reader decodes forward from
    the key frame before the requested one.

    The ``av`` package is optional: it is imported when the file is
    opened.

    Parameters
    ----------
    filename : str
        Path to the video file to read.
    '''

    def _initialize(self) -> bool:
        import av
        try:
            self._container = av.open(self.filename)
            self._stream = self._container.streams.video[0]
        except (av.error.FFmpegError, OSError, IndexError):
            return False
        self._stream.thread_type = 'AUTO'
        pixelFormat = self._stream.codec_context.pix_fmt
        self._format = (pixelFormat if pixelFormat in ('gray', 'gray16le')
                        else 'rgb24')
        self._start = self._stream.start_time or 0
        self._framenumber = 0
        self._decode(float('-inf'))
        return True

    def _deinitialize(self) -> None:
        self._container.close()

    def _decode(self, first: float) -> None:
        '''Decode from the current position, dropping frames before *first*.'''
        self._frames = self._container.decode(self._stream)
        self._first = first

    def read(self) -> QCamera.CameraData:
        '''Read the next frame from the video file.

        Returns
        -------
        tuple[bool, ndarray or None]
            ``(True, frame)`` on success, ``(False, None)`` at the end of
            the file.
        '''
        for frame in self._frames:
            if frame.pts is not None and frame.pts < self._first:
                continue  # the key frame before the one that was asked for
            self._framenumber += 1
            return True, frame.to_ndarray(format=self._format)
        return False, None

    @QtCore.Slot(int)
    def seek(self, framenumber: int) -> None:
        '''Seek to the specified frame number.'''
        stream = self._stream
        pts = self._start + round(framenumber / stream.guessed_rate
                                  / stream.time_base)
        self._container.seek(pts, stream=stream)
        self._decode(pts)
        self._framenumber = framenumber

    @property
    def fps(self) -> float:
        '''Frame rate of the video file [fps].'''
        return float(self._stream.guessed_rate)

    @property
    def length(self) -> int:
        '''Number of frames in the video file.

        Counted by the file if it keeps count, and estimated from its
        duration if not, which is exact for the files that
        :class:`~QVideo.dvr.QPyAVWriter.QPyAVWriter` writes.
        '''
        stream = self._stream
        if stream.frames:
            return stream.frames
        if stream.duration:
            seconds = stream.duration * stream.time_base
        else:
            seconds = (self._container.duration or 0) / 1_000_000
        return round(seconds * stream.guessed_rate)

    @property
    def framenumber(self) -> int:
        '''Index of the next frame to be returned by :meth:`read`.'''
        return self._framenumber

    @property
    def width(self) -> int:
        '''Frame width in pixels.'''
        return self._stream.codec_context.width

    @property
    def height(self) -> int:
        '''Frame height in pixels.'''
        return self._stream.codec_context.height


class QPyAVSource(QVideoSource):

    '''Video source for the files that :class:`QPyAVReader` reads.

    Parameters
    ----------
    reader : str, Path, or QPyAVReader
        Path to the video file to read, or an existing
        :class:`QPyAVReader` instance.
    '''

    def __init__(self, reader: str | Path | QPyAVReader) -> None:
        if isinstance(reader, (str, Path)):
            reader = QPyAVReader(str(reader))
        super().__init__(reader)
