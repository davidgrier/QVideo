'''Camera factory — discovers and returns the first available camera backend.

Provides :func:`Camera`, a model-agnostic entry point that discovers and
returns the first available camera backend.  The result is usable
immediately (``camera.read()``, property access) and is also awaitable —
``await Camera()`` in Jupyter probes all backends, prints which cameras
were found, and opens the first working one.

This module needs neither Jupyter nor ``ipywidgets``.  The notebook
features (the chooser, ``live_view`` and ``controls``) are in
:mod:`QVideo.interactive.widgets`, which is imported only when one of them
is used.
'''
import importlib
import logging
import time
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

import numpy as np

from QVideo.cameras import chooser
from QVideo.cameras.chooser import BACKENDS, available_cameras, discover
from QVideo.lib.QVideoFilter import prepare
from QVideo.lib.QImageSaver import QImageSaver
from QVideo.lib.imageops import save_image
from QVideo.lib.videotypes import FrameInfo

if TYPE_CHECKING:
    from QVideo.interactive.widgets import LiveView
    from QVideo.lib.videotypes import Image

logger = logging.getLogger(__name__)

__all__ = ['Camera', 'available_cameras']

#: How far the rate of the frames may be from the rate of the file [fraction].
_RATE_TOLERANCE = 0.1


def _unavailable(model: str) -> str:
    '''Return the reason the backend for *model* cannot be imported.'''
    try:
        importlib.import_module(BACKENDS[model.lower()].module)
    except ImportError as ex:
        return f':\n{ex}'
    return ''


def _report(working: list[tuple[str, int]]) -> None:
    '''Print available cameras and which one was selected.'''
    labels = [BACKENDS[k].label for k, _ in working]
    if len(labels) == 1:
        print(f'Camera: {labels[0]}')
        return
    others = ', '.join(f'Camera({label!r})' for label in labels[1:])
    print(f'Available cameras: {", ".join(labels)}')
    print(f'Using {labels[0]}. To select a different one: {others}')


async def _choose(working: list[tuple[str, int]]) -> tuple[str, int]:
    '''Return the camera to use among those that work.

    The simulated Noise camera is a fallback, not a choice: a single real
    camera is used without asking, and Noise alone says that no hardware
    was found.  A notebook with ``ipywidgets`` shows a drop-down when there
    are several real cameras; otherwise they are reported and the first is
    used.
    '''
    real = [camera for camera in working if camera[0] != 'noise']
    if not real:
        print('No camera hardware found; using the simulated Noise camera.')
        return working[0]
    if len(real) == 1:
        _report(real)
        return real[0]
    options = [(BACKENDS[k].label, (k, cid)) for k, cid in working]
    try:
        choose = _notebook('the camera chooser').choose
    except ImportError:
        _report(working)
        return working[0]
    print('Choose a camera and press Open.  If you see HBox(...) instead of '
          'a drop-down,\nthis Jupyter cannot show widgets: use '
          f'Camera({options[0][0]!r}) instead.')
    return await choose(options)


def _in_ipython() -> bool:
    '''Return True when running under IPython (a notebook or its shell).'''
    try:
        from IPython import get_ipython
    except ImportError:
        return False
    return get_ipython() is not None


def _notebook(feature: str) -> ModuleType:
    '''Return the Jupyter front end, which needs ipywidgets.'''
    try:
        return importlib.import_module('QVideo.interactive.widgets')
    except ImportError as ex:
        raise ImportError(
            f'ipywidgets is required for {feature}. '
            'Install it with: pip install ipywidgets') from ex


def _apply(filters: list, frame: 'Image',
           levels: 'tuple[float, float] | None' = None) -> 'Image | None':
    '''Run *frame* through *filters*, in order.

    Returns ``None`` if a filter has no result yet (a filter that averages
    over several frames, for example).  A filter that raises is reported
    and removed from *filters*, as the pipeline of a Qt application does.
    A ``uint16`` frame (from a camera of more than 8 bits, with *levels*)
    reaches a filter that is not ``deep`` as ``uint8``, scaled between its
    levels, as in the pipeline.
    '''
    for video_filter in list(filters):
        try:
            frame, levels = prepare(video_filter, frame, levels)
            frame = video_filter(frame)
        except Exception as ex:
            name = getattr(video_filter, '__name__',
                           type(video_filter).__name__)
            logger.warning(f'{name} failed and was removed from '
                           f'camera.filters: {ex}')
            filters.remove(video_filter)
            continue
        if frame is None:
            return None
    return frame


class _CameraProxy:
    '''Wraps discovered camera backends; usable immediately and awaitable.

    Attribute access and ``read()`` are forwarded to the first successfully
    opened backend.  ``await proxy`` in a Jupyter cell probes all candidates,
    prints which cameras were found, and opens the first working one.

    ``filters`` is a list of callables that ``read()`` (and so
    ``live_view()``) applies to every frame, in order.
    '''

    def __init__(self, candidates: list[tuple[str, int]]) -> None:
        object.__setattr__(self, '_candidates', candidates)
        object.__setattr__(self, '_selected_key', None)
        object.__setattr__(self, '_camera', None)
        object.__setattr__(self, '_live_view', None)
        object.__setattr__(self, '_filters', [])

    @property
    def filters(self) -> list:
        '''Callables that :meth:`read` applies to every frame, in order.

        Any callable that takes a frame and returns a frame will do,
        including the filters in :mod:`QVideo.filters`.  Assign a list, or
        change the list in place::

            camera.filters = [DarkFrameFilter(), GammaFilter()]
            camera.filters.append(EdgeFilter())

        A filter that raises is reported and removed.  A filter that has no
        result yet, such as an average over several frames, makes
        :meth:`read` take another frame.  ``camera.filters = []`` returns
        to raw frames.
        '''
        return self._filters

    @filters.setter
    def filters(self, filters) -> None:
        object.__setattr__(self, '_filters', list(filters))

    def _ensure_open(self) -> None:
        '''Open the first candidate that works, unless one is open.'''
        if self._camera is not None:
            return
        key, camera = chooser.open_first(self._candidates)
        object.__setattr__(self, '_selected_key', key)
        object.__setattr__(self, '_camera', camera)

    def read(self) -> 'Image':
        '''Read one frame, apply :attr:`filters`, return it as an array.'''
        self._ensure_open()
        camera = self._camera
        while True:
            ok, frame = camera.saferead()
            if not ok or frame is None:
                raise RuntimeError('Camera read failed')
            frame = _apply(self.filters, frame,
                           getattr(camera, 'levels', None))
            if frame is not None:
                return frame

    def frames(self, n: int) -> list['Image']:
        '''Read *n* consecutive frames, with :attr:`filters` applied.

        Parameters
        ----------
        n : int
            The number of frames, at least 1.

        Returns
        -------
        list
            *n* arrays, each as :meth:`read` returns it.

        Raises
        ------
        ValueError
            If *n* is less than 1.
        '''
        if n < 1:
            raise ValueError(f'n must be at least 1, not {n}')
        return [self.read() for _ in range(n)]

    def stack(self, n: int) -> 'Image':
        '''Read *n* consecutive frames as one array.

        Returns
        -------
        numpy.ndarray
            The frames along a new first axis: ``(n, height, width)`` for
            a gray camera, ``(n, height, width, 3)`` for a color one.
            Memory grows with *n*: 100 frames of 1920 x 1200 at 16 bits
            take about 460 MB.

        Raises
        ------
        ValueError
            If *n* is less than 1.
        '''
        return np.stack(self.frames(n))

    def save(self, filename: 'str | Path | None' = None,
             image: 'Image | None' = None) -> str:
        '''Save a frame to a file and return its path.

        Parameters
        ----------
        filename : str or Path, optional
            Where to save it; the extension sets the format (``.png``,
            ``.tiff`` and ``.jpg`` among others).  Default:
            ``camera_<YYYYMMDD>_<HHMMSS>.png`` in the current directory,
            without replacing a file that exists.
        image : numpy.ndarray, optional
            What to save, such as a result of your own analysis.  Default:
            a new frame from :meth:`read`.

        Returns
        -------
        str
            The path that was written.

        Raises
        ------
        ValueError
            If the type or the shape of the image cannot be saved.
        OSError
            If the file cannot be written.

        Notes
        -----
        A gray frame of more than 8 bits goes to a 16 bit PNG or TIFF,
        stretched so that the levels of the camera run from 0 to 65535;
        in any other format it gets 8 bits.  See
        :func:`~QVideo.lib.imageops.save_image`.
        '''
        if image is None:
            image = self.read()
        path = str(filename) if filename else \
            QImageSaver(prefix='camera').defaultPath()
        save_image(image, path, getattr(self._camera, 'levels', None))
        return path

    def record(self, filename: 'str | Path', n: int | None = None,
               seconds: float | None = None, fps: float | None = None,
               overwrite: bool = False) -> str:
        '''Record filtered frames to a video file and return its path.

        The call returns when the recording is complete, so a cell can run
        an experiment and move on.  It reads in the thread of the caller,
        and the interrupt button of the notebook stops it with the file
        closed and readable.

        Parameters
        ----------
        filename : str or Path
            The file to write; its extension chooses the format, as in the
            DVR panel (``.mkv`` and ``.avi`` are lossless, ``.mp4`` is
            lossy, ``.h5`` keeps the time of every frame).
        n : int, optional
            Stop after this many frames.
        seconds : float, optional
            Stop after this many seconds.  Give *n*, *seconds* or both
            (the first limit that is reached ends the recording).
        fps : float, optional
            The frame rate that the file declares.  Default: the frame
            rate that the camera reports, or 30.  A video plays back at
            this rate, whatever the speed of the filters.
        overwrite : bool
            Replace *filename* if it exists.  By default an existing file
            is an error.

        Returns
        -------
        str
            The path that was written.

        Raises
        ------
        ValueError
            If neither *n* nor *seconds* is given, or one of them is less
            than 1 frame or 0 seconds, or the extension is not supported.
        FileExistsError
            If *filename* exists and *overwrite* is ``False``.
        RuntimeError
            If the camera fails to deliver a frame, or the writer stops
            early (a frame whose size changed, a disk that is full).  The
            frames written until then stay in the file.

        Notes
        -----
        A frame of more than 8 bits goes to a lossless ``.mkv``, ``.avi``
        or ``.h5`` file as it is.  An ``.mp4`` file holds 8 bits, so the
        frames are scaled between the levels of the camera, and the log
        says so.

        The frame rate that the camera reports may not be the one that it
        delivers (a webcam slows down in dim light), and a slow filter or
        disk makes the loop miss frames.  If *fps* is not given and the
        frames arrived at a rate more than 10% off the rate the file
        declares, the log warns, with the measured rate: the video would
        play too fast or too slow.  Record again with ``fps=`` set to it.
        '''
        from QVideo.dvr import formats
        if n is None and seconds is None:
            raise ValueError('give n, the number of frames, or seconds')
        if n is not None and n < 1:
            raise ValueError(f'n must be at least 1, not {n}')
        if seconds is not None and seconds <= 0:
            raise ValueError(f'seconds must be positive, not {seconds}')
        path = str(filename)
        self._ensure_open()
        rate = fps or getattr(self._camera, 'fps', None) or 30.
        writer = formats.openWriter(path, rate, n or 2**31,
                                    overwrite=overwrite)
        reasons: list[str] = []
        writer.finished.connect(reasons.append)
        start = first = last = time.perf_counter()
        count = 0
        try:
            while not reasons and (n is None or count < n) and (
                    seconds is None
                    or time.perf_counter() - start < seconds):
                frame = self.read()
                levels = (getattr(self._camera, 'levels', None)
                          if frame.dtype == np.uint16 else None)
                last = time.perf_counter()
                if count == 0:
                    first = last
                writer.write(frame, FrameInfo(count, last, levels=levels))
                count += 1
        finally:
            writer.close()
        if any(reasons):
            raise RuntimeError(f'recording stopped after {writer.framenumber}'
                               f' frames: {reasons[0]}')
        logger.info(f'Recorded {count} frames to {path!r} '
                    f'in {time.perf_counter() - start:.1f} s')
        if not fps and count > 1 and last > first:
            measured = (count - 1) / (last - first)
            if abs(measured - rate) > _RATE_TOLERANCE * rate:
                logger.warning(
                    f'The frames arrived at {measured:.1f} frames/s, not '
                    f'the {rate:.1f} that {path!r} declares, so the video '
                    f'plays {rate / measured:.1f} times as fast as it '
                    f'happened.  Record again with fps={measured:.1f}.')
        return path

    def __getattr__(self, name: str):
        # IPython probes a displayed object for names such as
        # ``_repr_html_``, and copy and pickle for dunder names: none of
        # those may open the camera.  A property of a camera is public.
        if name.startswith('_'):
            raise AttributeError(name)
        self._ensure_open()
        return getattr(self._camera, name)

    def __setattr__(self, name: str, value) -> None:
        if name == 'filters':
            object.__setattr__(self, name, value)
            return
        self._ensure_open()
        setattr(self._camera, name, value)

    def __repr__(self) -> str:
        key = self._selected_key
        label = BACKENDS[key].label if key else 'uninitialized'
        return f'<Camera: {label}>'

    def live_view(self, fps: float = 30.0) -> 'LiveView':
        '''Display a live video feed in a Jupyter cell.

        Encodes each frame as JPEG and streams it into an
        :mod:`ipywidgets` ``Image`` widget via an ``asyncio`` background
        loop.  No matplotlib backend switching required.

        Parameters
        ----------
        fps : float
            Target display update rate in frames per second (default 30).

        Returns
        -------
        LiveView
            Handle for the running feed.  Call :meth:`LiveView.stop`
            to end it.

        Raises
        ------
        ImportError
            If :mod:`ipywidgets` is not installed.

        Notes
        -----
        A camera of more than 8 bits gets a drop-down under the picture
        that scales its counts for the browser: the range of the camera,
        auto contrast or the full 16 bits.

        The proxy keeps an internal reference to the handle, so you can
        stop the feed from any cell via :meth:`stop_live_view`::

            camera.live_view()
            # ... in a later cell ...
            camera.stop_live_view()

        Alternatively, keep the returned handle and call its
        :meth:`LiveView.stop` method directly::

            live = camera.live_view()
            live.stop()
        '''
        jupyter = _notebook('live_view()')
        self._ensure_open()
        lv = jupyter.live_view(
            self.read, fps,
            levels=lambda: getattr(self._camera, 'levels', None))
        object.__setattr__(self, '_live_view', lv)
        return lv

    def show(self, image: 'Image | None' = None,
             contrast: 'str | tuple[float, float]' = 'auto') -> None:
        '''Show one frame in the cell.

        Parameters
        ----------
        image : numpy.ndarray, optional
            What to show.  Default: a new frame from :meth:`read`.
        contrast : str or tuple
            How a frame of more than 8 bits is scaled to the 8 bits of the
            display: ``'auto'`` (the 1st and 99th percentiles, the
            default), ``'camera'`` (the range of the camera), ``'full'``
            (0 to 65535) or ``(black, white)``.  An 8 bit frame is shown as
            it is.

        Raises
        ------
        ImportError
            If :mod:`ipywidgets` is not installed.
        ValueError
            If *contrast* is not one of these.
        '''
        jupyter = _notebook('show()')
        if image is None:
            image = self.read()
        jupyter.show(image, contrast,
                     getattr(self._camera, 'levels', None))

    def stop_live_view(self) -> None:
        '''Stop the live video feed started by :meth:`live_view`.

        Cancels the background update loop.  Safe to call even if no
        feed is running.

        Examples
        --------
        ::

            camera = await Camera()
            camera.live_view()
            # ... in a later cell ...
            camera.stop_live_view()
        '''
        lv = self._live_view
        if lv is not None:
            lv.stop()
            object.__setattr__(self, '_live_view', None)

    def controls(self):
        '''Return an interactive property panel for use in Jupyter.

        Creates a :class:`~QVideo.interactive.widgets.CameraControls`
        widget that exposes all registered camera properties as editable
        inputs.
        Read-only properties are shown but disabled.  A **Refresh** button
        re-reads all values from the camera.

        Returns
        -------
        CameraControls
            An :mod:`ipywidgets`-based panel.  In a Jupyter cell, assign
            it to the last expression or call
            :func:`IPython.display.display` on it to render it.

        Raises
        ------
        ImportError
            If :mod:`ipywidgets` is not installed.

        Examples
        --------
        ::

            camera = await Camera()
            camera.controls()
        '''
        self._ensure_open()
        controls = _notebook('camera.controls()').CameraControls
        return controls(self._camera)

    def __await__(self):
        return self._select().__await__()

    async def _select(self) -> '_CameraProxy':
        '''Probe the candidates, let a notebook choose, and open one.'''
        candidates = self._candidates
        if len(candidates) > 1 and _in_ipython():
            working = chooser.working(candidates)
            if working:
                chosen = await _choose(working)
                object.__setattr__(self, '_candidates', [chosen])
        self._ensure_open()
        return self


def Camera(model: str | None = None, cameraID: int = 0) -> _CameraProxy:
    '''Discover and return a camera backend.

    Parameters
    ----------
    model : str or None
        Camera model name (case-insensitive): ``'Basler'``, ``'Flir'``,
        ``'OpenCV'``, ``'Noise'``, etc.  When ``None``, all installed
        backends are probed in priority order.
    cameraID : int
        Device index passed to the backend (default 0).

    Returns
    -------
    _CameraProxy
        Proxy around the selected camera backend.  Usable immediately
        (``camera.read()``, property access) and awaitable —
        ``await Camera()`` in Jupyter probes all backends, prints which
        cameras were found, and opens the first working one.

    Raises
    ------
    RuntimeError
        If no matching camera backend is available.
    ValueError
        If *model* is not a recognized backend name.

    Examples
    --------
    Acquire a single frame from the first available camera::

        camera = Camera()
        frame = camera.read()

    Use in Jupyter — prints available cameras and opens the first one::

        camera = await Camera()
        frame = camera.read()

    Request a specific backend::

        camera = Camera('Noise')
        frame = camera.read()
    '''
    candidates = discover(model, cameraID)
    if not candidates:
        raise RuntimeError(
            'No camera available'
            + (f' for model {model!r}{_unavailable(model)}' if model else '')
        )
    return _CameraProxy(candidates)
