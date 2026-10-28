'''PyAV video file writer: lossless FFV1 and H.264 through FFmpeg.'''
from fractions import Fraction
from pathlib import Path
import numpy as np
from QVideo.lib import QVideoWriter
from QVideo.lib.videotypes import Image, FrameInfo
import logging


__all__ = ['QPyAVWriter']


logger = logging.getLogger(__name__)

#: The pixel format that PyAV is given, by number of dimensions and dtype.
_FORMATS = {(2, np.uint8): 'gray',
            (2, np.uint16): 'gray16le',
            (3, np.uint8): 'rgb24'}


class QPyAVWriter(QVideoWriter):

    '''Video file writer that uses PyAV, the Python binding of FFmpeg.

    ``.avi`` and ``.mkv`` files are compressed without loss by FFV1, which
    returns every pixel of 8-bit gray, 16-bit gray and 8-bit color frames
    as it was written, and is several times faster than the same codec in
    OpenCV.  ``.mp4`` files are compressed by H.264, with a small loss.
    The file is opened lazily on the first frame so that frame dimensions
    and color mode can be determined automatically.

    The ``av`` package is optional: it is imported when the first file is
    opened.

    Parameters
    ----------
    filename : str
        Path to the output video file.
    *args :
        Forwarded to :class:`~QVideo.lib.QVideoWriter`.
    **kwargs :
        Forwarded to :class:`~QVideo.lib.QVideoWriter`.

    Attributes
    ----------
    CODEC_MAP : dict[str, tuple[str, dict[str, str]]]
        Maps file extensions to the name of the FFmpeg encoder and its
        options.
    '''

    CODEC_MAP: dict[str, tuple[str, dict[str, str]]] = {
        '.avi': ('ffv1', {}),
        '.mkv': ('ffv1', {}),
        '.mp4': ('libx264', {'crf': '18', 'preset': 'veryfast'}),
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # Import here, in the thread that makes the writer, not on the
        # first frame: the import takes a second or more when the files
        # are not cached, and the camera does not wait for it.
        import av
        self._av = av
        self._container = None
        self._stream = None
        self._format = None
        self._index = 0

    def open(self, frame: Image) -> bool:
        '''Open the video file using the encoder of its extension.

        Called automatically by :meth:`~QVideo.lib.QVideoWriter.write`
        on the first frame.

        Parameters
        ----------
        frame : Image
            The first video frame, used to determine dimensions and
            pixel format.

        Returns
        -------
        bool
            ``True`` if the file was opened; ``False`` if the frames or
            the extension are not supported or the encoder cannot start.
        '''
        av = self._av
        suffix = Path(self.filename).suffix
        self._format = _FORMATS.get((frame.ndim, frame.dtype.type))
        if self._format is None or suffix not in self.CODEC_MAP:
            logger.warning(f'Cannot write {frame.dtype} frames of shape '
                           f'{frame.shape} to {self.filename!r}')
            return False
        codec, options = self.CODEC_MAP[suffix]
        try:
            container = av.open(self.filename, 'w')
            stream = container.add_stream(
                codec, rate=Fraction(self.fps).limit_denominator(1001))
            stream.height, stream.width = frame.shape[:2]
            stream.pix_fmt = self._pixelFormat(codec)
            stream.options = options
            stream.codec_context.open()
            container.start_encoding()  # create the file now, not later
        except (av.error.FFmpegError, OSError, ValueError) as ex:
            logger.warning(f'Could not open {self.filename!r}: {ex}')
            return False
        self._container, self._stream = container, stream
        self._index = 0
        return True

    def _pixelFormat(self, codec: str) -> str:
        '''Return the pixel format in which *codec* stores the frames.'''
        if codec == 'libx264':
            return 'yuv420p'
        return 'bgr0' if self._format == 'rgb24' else self._format

    def isOpen(self) -> bool:
        '''Return ``True`` if the video file is currently open.'''
        return self._container is not None

    def _write(self, frame: Image, info: FrameInfo | None = None) -> None:
        '''Write *frame* to the video file.

        The capture metadata *info* is not stored: the frames are
        written at a constant frame rate.
        '''
        picture = self._av.VideoFrame.from_ndarray(
            np.ascontiguousarray(frame), format=self._format)
        picture.pts = self._index
        self._index += 1
        for packet in self._stream.encode(picture):
            self._container.mux(packet)

    def close(self) -> None:
        '''Write out the frames still in the encoder and close the file.'''
        if self.isOpen():
            for packet in self._stream.encode():
                self._container.mux(packet)
            self._container.close()
        self._container = None
        self._stream = None
