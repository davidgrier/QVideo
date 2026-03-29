from QVideo.lib import QVideoWriter
from QVideo.lib.videotypes import Image
from pyqtgraph.Qt import QtCore
from pathlib import Path
import cv2
import logging


__all__ = ['QOpenCVWriter']


logger = logging.getLogger(__name__)


class QOpenCVWriter(QVideoWriter):

    '''OpenCV-backed video file writer supporting AVI, MKV, and MP4.

    Writes frames to a video file using ``cv2.VideoWriter``.  The file
    is opened lazily on the first frame so that frame dimensions and
    colour mode can be determined automatically.

    Codecs are selected based on the file extension using
    :attr:`CODEC_MAP`.  When no codec is specified, the preference-ordered
    list for the extension is probed and the first one OpenCV accepts is
    used.  Specifying *codec* explicitly bypasses probing.

    If the shape of a subsequent frame differs from the first, recording
    stops immediately and :attr:`~QVideo.lib.QVideoWriter.finished` is
    emitted.

    Parameters
    ----------
    filename : str
        Path to the output video file.
    codec : str or None
        Four-character codec code passed to ``cv2.VideoWriter_fourcc``.
        If ``None``, codecs are chosen from :attr:`CODEC_MAP` based on
        the file extension.
    *args :
        Forwarded to :class:`~QVideo.lib.QVideoWriter`.
    **kwargs :
        Forwarded to :class:`~QVideo.lib.QVideoWriter`.

    Attributes
    ----------
    CODEC_MAP : dict[str, tuple[str, ...]]
        Maps file extensions to preference-ordered codec codes.
    '''

    CODEC_MAP: dict[str, tuple[str, ...]] = {
        '.avi': ('FFV1', 'HFYU'),
        '.mkv': ('FFV1', 'HFYU'),
        '.mp4': ('avc1', 'mp4v'),
    }

    def __init__(self, *args,
                 codec: str | None = None,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if codec is not None:
            self._codecs = (codec,)
        else:
            suffix = Path(self.filename).suffix
            self._codecs = self.CODEC_MAP.get(suffix, ())
        self._writer = None
        self._shape = None

    def open(self, frame: Image) -> bool:
        '''Open the video file using the first available codec.

        Called automatically by :meth:`~QVideo.lib.QVideoWriter.write`
        on the first frame.  Frame dimensions and colour mode are
        determined from *frame*; codecs are probed via :meth:`_getWriter`.

        Parameters
        ----------
        frame : Image
            The first video frame, used to determine dimensions and
            colour mode.

        Returns
        -------
        bool
            ``True`` if a codec was found and the file was opened;
            ``False`` otherwise.
        '''
        color = (frame.ndim == 3)
        self._writer = self._getWriter(frame.shape, color)
        if self._writer is not None:
            self._shape = frame.shape
            return True
        return False

    def _getWriter(self, shape: tuple[int, ...], color: bool) -> cv2.VideoWriter | None:
        '''Probe codecs in preference order and return the first that opens.

        Parameters
        ----------
        shape : tuple[int, ...]
            Frame shape ``(height, width)`` used to configure the writer.
        color : bool
            ``True`` for colour frames, ``False`` for grayscale.

        Returns
        -------
        cv2.VideoWriter or None
            An open ``cv2.VideoWriter``, or ``None`` if no codec succeeded.
        '''
        h, w = shape[:2]
        for codec in self._codecs:
            fourcc = cv2.VideoWriter_fourcc(*codec)
            writer = cv2.VideoWriter(
                self.filename, fourcc, self.fps, (w, h), color)
            if writer.isOpened():
                logger.debug(f'Opened {self.filename!r} with codec {codec!r}')
                return writer
            writer.release()
            logger.debug(f'Codec {codec!r} not available')
        logger.warning(f'No supported codec available for {self.filename!r}')
        return None

    def isOpen(self) -> bool:
        '''Return ``True`` if the video file is currently open.'''
        return (self._writer is not None) and self._writer.isOpened()

    def _write(self, frame: Image) -> None:
        if frame.shape != self._shape:
            logger.warning(
                f'Frame shape {frame.shape} does not match '
                f'expected {self._shape}: stopping recording')
            self.finished.emit()
            return
        if frame.ndim == 3:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        self._writer.write(frame)

    @QtCore.pyqtSlot()
    def close(self) -> None:
        '''Release the video file and reset internal state.'''
        if self.isOpen():
            self._writer.release()
        self._writer = None
        self._shape = None
