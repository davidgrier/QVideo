'''Run a neural network with the DNN module of OpenCV.

:class:`DNN` loads a network (an ONNX file, or anything else that
``cv2.dnn.readNet`` reads), turns a video frame into the input that the
network wants and returns what the network computes.  It has no Qt in it, so
a filter, an overlay worker or a script can use it, and it can be tested
without an interface.  What the output means (boxes, a mask, an upscaled
image) is for the caller to decide; :func:`letterbox` helps with the
networks that want an input of a fixed size.

OpenCV 5 runs the new DNN engine, which works on the CPU.  The standard
``opencv-python`` wheels have no CUDA support: a GPU needs OpenCV built from
source, or another runtime.
'''
from collections.abc import Sequence
from pathlib import Path
import cv2
import numpy as np
from QVideo.lib.imageops import to8bit
from QVideo.lib.videotypes import Image


__all__ = ['DNN', 'letterbox', 'prepare']


def prepare(image: Image) -> Image:
    '''Return *image* as the ``uint8`` RGB frame that a network is given.

    A gray frame becomes three equal channels, a frame with an alpha
    channel loses it and a ``uint16`` frame is scaled to eight bits over its
    whole range.

    Parameters
    ----------
    image : Image
        Gray frame of shape ``(H, W)`` or color frame of shape
        ``(H, W, 3)`` or ``(H, W, 4)``, ``uint8`` or ``uint16``.
    '''
    if image.dtype == np.uint16:
        image = to8bit(image)
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    if image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)
    return image


def letterbox(image: Image,
              size: tuple[int, int],
              color: int = 114) -> tuple[Image, float, tuple[float, float]]:
    '''Fit *image* in a frame of *size* without changing its aspect ratio.

    The image is scaled to the largest size that fits and centered, and the
    margins are filled with *color* (gray, as the YOLO networks were
    trained).

    Parameters
    ----------
    image : Image
        Color frame of shape ``(H, W, 3)``.
    size : tuple of int
        ``(width, height)`` of the result.
    color : int
        Value of the margins.

    Returns
    -------
    image : Image
        The frame of *size*.
    scale : float
        The factor by which the image was scaled.
    pad : tuple of float
        ``(x, y)`` offset of the image in the result.  A point ``p`` of the
        result is at ``(p - pad) / scale`` in the original image.
    '''
    width, height = size
    h, w = image.shape[:2]
    scale = min(width / w, height / h)
    nw, nh = round(w * scale), round(h * scale)
    resized = cv2.resize(image, (nw, nh), interpolation=cv2.INTER_LINEAR) \
        if (nw, nh) != (w, h) else image
    dx, dy = (width - nw) / 2, (height - nh) / 2
    top, left = int(dy), int(dx)
    padded = cv2.copyMakeBorder(
        resized, top, height - nh - top, left, width - nw - left,
        cv2.BORDER_CONSTANT, value=(color,) * 3)
    return padded, scale, (float(left), float(top))


class DNN:

    '''A network that OpenCV runs on frames.

    Parameters
    ----------
    path : str
        File that holds the network, usually ``.onnx``.
    size : tuple of int or None
        ``(width, height)`` to which a frame is resized to make the input.
        ``None`` keeps the size of the frame, for a network that takes any.
    scale : float
        Factor by which pixel values are multiplied.  Default: ``1/255``,
        which gives values between 0 and 1.
    mean : float or tuple of float
        Value subtracted from the pixels before they are scaled.
    swapRB : bool
        Swap the red and blue channels.  Frames are RGB, which most
        networks expect, so the default is ``False``.
    engine : int or None
        The DNN engine, one of the ``cv2.dnn.ENGINE_*`` constants.
        ``None`` lets OpenCV choose: the new engine first, the classic one
        if it cannot read the network.
    backend, target : int or None
        ``cv2.dnn.DNN_BACKEND_*`` and ``DNN_TARGET_*`` constants for the
        classic engine, the only one that offers more than the CPU.  They
        are left alone when ``None``.

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    RuntimeError
        If OpenCV cannot read the network.
    '''

    def __init__(self,
                 path: str,
                 size: tuple[int, int] | None = None,
                 scale: float = 1 / 255.,
                 mean: float | Sequence[float] = 0.,
                 swapRB: bool = False,
                 engine: int | None = None,
                 backend: int | None = None,
                 target: int | None = None) -> None:
        if not Path(path).is_file():
            raise FileNotFoundError(f'No network file {str(path)!r}')
        if engine is None:
            engine = cv2.dnn.ENGINE_AUTO
        try:
            self.net = cv2.dnn.readNet(str(path), '', '', engine)
        except cv2.error as err:
            raise RuntimeError(
                f'OpenCV could not read the network {str(path)!r}: '
                f'{err.msg.strip()}') from err
        if backend is not None:
            self.net.setPreferableBackend(backend)
        if target is not None:
            self.net.setPreferableTarget(target)
        self.size = size
        self.scale = scale
        self.mean = mean
        self.swapRB = swapRB
        self._outputs = self.net.getUnconnectedOutLayersNames()

    def blob(self, image: Image) -> np.ndarray:
        '''Return the input of the network made from *image*.

        The result has shape ``(1, 3, H, W)`` and type ``float32``.
        '''
        mean = self.mean
        if isinstance(mean, (int, float)):
            mean = (mean,) * 3
        return cv2.dnn.blobFromImage(
            prepare(image), self.scale, self.size or (0, 0), tuple(mean),
            swapRB=self.swapRB, crop=False)

    def forward(self, image: Image) -> list[np.ndarray]:
        '''Run the network on *image* and return its outputs.

        Parameters
        ----------
        image : Image
            Gray or color frame.

        Returns
        -------
        list of numpy.ndarray
            One array for each output of the network.
        '''
        self.net.setInput(self.blob(image))
        outputs = self.net.forward(self._outputs)
        return [outputs] if isinstance(outputs, np.ndarray) \
            else list(outputs)
