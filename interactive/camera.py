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
from typing import TYPE_CHECKING
from QVideo.cameras import chooser
from QVideo.cameras.chooser import BACKENDS, available_cameras, discover

if TYPE_CHECKING:
    from QVideo.interactive.widgets import LiveView
    from QVideo.lib.videotypes import Image

logger = logging.getLogger(__name__)

__all__ = ['Camera', 'available_cameras']


def _unavailable(model: str) -> str:
    '''Return the reason the backend for *model* cannot be imported.'''
    try:
        importlib.import_module(BACKENDS[model.lower()].module)
    except (ImportError, ModuleNotFoundError) as ex:
        return f':\n{ex}'
    return ''


def _report(working: list[tuple[str, int]]) -> None:
    '''Print available cameras and which one was selected.'''
    labels = [BACKENDS[k].label for k, _ in working]
    if len(labels) == 1:
        print(f'Camera: {labels[0]}')
    else:
        opts = ', '.join(f"Camera('{l}')" for l in labels[1:])
        print(f'Available cameras: {", ".join(labels)}')
        print(f'Using {labels[0]}. To select a different one: {opts}')


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
    try:
        options = [(BACKENDS[k].label, (k, cid)) for k, cid in working]
        choose = _notebook('the camera chooser').choose
    except ImportError:
        _report(working)
        return working[0]
    print('Choose a camera and press Open.  If you see HBox(...) instead of '
          'a drop-down,\nthis Jupyter cannot show widgets: use '
          f"Camera('{options[0][0]}') instead.")
    return await choose(options)


def _in_ipython() -> bool:
    '''Return True when running under IPython (a notebook or its shell).'''
    try:
        from IPython import get_ipython
    except ImportError:
        return False
    return get_ipython() is not None


def _notebook(feature: str):
    '''Return the Jupyter front end, which needs ipywidgets.'''
    try:
        return importlib.import_module('QVideo.interactive.widgets')
    except ImportError as ex:
        raise ImportError(
            f'ipywidgets is required for {feature}. '
            'Install it with: pip install ipywidgets') from ex


def _apply(filters: list, frame: 'Image') -> 'Image | None':
    '''Run *frame* through *filters*, in order.

    Returns ``None`` if a filter has no result yet (a filter that averages
    over several frames, for example).  A filter that raises is reported
    and removed from *filters*, as the pipeline of a Qt application does.
    '''
    for video_filter in list(filters):
        try:
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
        if self._camera is not None:
            return
        candidates = self._candidates
        key, camera = chooser.open_first(candidates)
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
            frame = _apply(self.filters, frame)
            if frame is not None:
                return frame

    def __getattr__(self, name: str):
        if name.startswith('__'):  # copy and pickle probe for these
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
        The proxy keeps an internal reference to the handle, so you can
        stop the feed from any cell via :meth:`stop_live_view`::

            camera.live_view()
            # ... in a later cell ...
            camera.stop_live_view()

        Alternatively, keep the returned handle and call its
        :meth:`LiveView.stop` method directly::

            live = camera.live_view()
            live.stop()

        Examples
        --------
        ::

            camera = await Camera()
            camera.live_view()
            # ...
            camera.stop_live_view()
        '''
        jupyter = _notebook('live_view()')
        self._ensure_open()
        lv = jupyter.live_view(self.read, fps)
        object.__setattr__(self, '_live_view', lv)
        return lv

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
