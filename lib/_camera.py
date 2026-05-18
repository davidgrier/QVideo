'''Camera factory — discovers and returns the first available camera backend.

Provides :func:`Camera`, a model-agnostic entry point that discovers and
returns the first available camera backend.  The result is usable
immediately (``camera.read()``, property access) and is also awaitable —
``await Camera()`` in Jupyter probes all backends, prints which cameras
were found, and opens the first working one.
'''
import contextlib
import importlib
import logging
from typing import NamedTuple, TYPE_CHECKING

if TYPE_CHECKING:
    from QVideo.lib.videotypes import Image

logger = logging.getLogger(__name__)

__all__ = ['Camera']


class _BackendEntry(NamedTuple):
    module: str
    camera_cls: str
    tree_cls: str
    label: str


_BACKENDS: dict[str, _BackendEntry] = {
    'basler':   _BackendEntry('QVideo.cameras.Basler',   'QBaslerCamera',   'QBaslerTree',   'Basler'),
    'flir':     _BackendEntry('QVideo.cameras.Flir',     'QFlirCamera',     'QFlirTree',     'Flir'),
    'ids':      _BackendEntry('QVideo.cameras.IDS',      'QIDSCamera',      'QIDSTree',      'IDS'),
    'mv':       _BackendEntry('QVideo.cameras.MV',       'QMVCamera',       'QMVTree',       'MV'),
    'vimbax':   _BackendEntry('QVideo.cameras.Vimbax',   'QVimbaXCamera',   'QVimbaXTree',   'VimbaX'),
    'picamera': _BackendEntry('QVideo.cameras.Picamera', 'QPicamera',       'QPicameraTree', 'Picamera'),
    'opencv':   _BackendEntry('QVideo.cameras.OpenCV',   'QOpenCVCamera',   'QOpenCVTree',   'OpenCV'),
    'noise':    _BackendEntry('QVideo.cameras.Noise',    'QNoiseCamera',    'QNoiseTree',    'Noise'),
}

_DISCOVERY_ORDER = ['basler', 'flir', 'ids', 'mv', 'vimbax', 'picamera', 'opencv', 'noise']


def _probe(key: str) -> bool:
    '''Return True if the backend module can be imported.'''
    try:
        importlib.import_module(_BACKENDS[key].module)
        return True
    except (ImportError, ModuleNotFoundError):
        return False


def _ensure_qapp() -> None:
    '''Create a QApplication if none exists (required before instantiating any QCamera).'''
    from qtpy.QtWidgets import QApplication
    if QApplication.instance() is None:
        QApplication([])


def _open(key: str, camera_id: int = 0):
    '''Import and instantiate (open) the camera for *key*. Returns None on failure.'''
    _ensure_qapp()
    entry = _BACKENDS[key]
    try:
        module = importlib.import_module(entry.module)
        cls = getattr(module, entry.camera_cls)
        return cls(cameraID=camera_id)
    except Exception as ex:
        logger.warning(f'Could not open {entry.label}: {ex}')
        return None


def _discover(model: str | None, camera_id: int = 0) -> list[tuple[str, int]]:
    '''Return (backend_key, camera_id) pairs for importable backends.'''
    if model is not None:
        key = model.lower()
        if key not in _BACKENDS:
            raise ValueError(
                f'Unknown camera model {model!r}. '
                f'Available: {sorted(_BACKENDS)}'
            )
        return [(key, camera_id)] if _probe(key) else []
    return [(key, camera_id) for key in _DISCOVERY_ORDER if _probe(key)]


@contextlib.contextmanager
def _quiet():
    '''Suppress all sub-ERROR log messages from QVideo loggers during probing.'''
    root = logging.getLogger('QVideo')
    saved = root.level
    root.setLevel(logging.ERROR)
    try:
        yield
    finally:
        root.setLevel(saved)


def _working_candidates(candidates: list[tuple[str, int]]) -> list[tuple[str, int]]:
    '''Return only the candidates whose cameras open successfully.'''
    working = []
    with _quiet():
        for key, camera_id in candidates:
            cam = _open(key, camera_id)
            if cam is not None and cam.isOpen():
                cam.close()
                working.append((key, camera_id))
    return working


def _jupyter_report(working: list[tuple[str, int]]) -> None:
    '''Print available cameras and which one was selected.'''
    labels = [_BACKENDS[k].label for k, _ in working]
    if len(labels) == 1:
        print(f'Camera: {labels[0]}')
    else:
        opts = ', '.join(f"Camera('{l}')" for l in labels[1:])
        print(f'Available cameras: {", ".join(labels)}')
        print(f'Using {labels[0]}. To select a different one: {opts}')


class _LiveView:
    '''Handle for a running :meth:`_CameraProxy.live_view` feed.

    Returned by :meth:`_CameraProxy.live_view`.  Call :meth:`stop` to
    end the update loop.
    '''

    def __init__(self, task) -> None:
        self._task = task

    def stop(self) -> None:
        '''Cancel the background update loop.'''
        self._task.cancel()


class _CameraProxy:
    '''Wraps discovered camera backends; usable immediately and awaitable.

    Attribute access and ``read()`` are forwarded to the first successfully
    opened backend.  ``await proxy`` in a Jupyter cell probes all candidates,
    prints which cameras were found, and opens the first working one.
    '''

    def __init__(self, candidates: list[tuple[str, int]]) -> None:
        object.__setattr__(self, '_candidates', candidates)
        object.__setattr__(self, '_selected_key', None)
        object.__setattr__(self, '_camera', None)

    def _ensure_open(self) -> None:
        if object.__getattribute__(self, '_camera') is not None:
            return
        candidates = object.__getattribute__(self, '_candidates')
        hardware = [k for k, _ in candidates if k != 'noise']
        with _quiet():
            for key, camera_id in candidates:
                cam = _open(key, camera_id)
                if cam is not None and cam.isOpen():
                    object.__setattr__(self, '_camera', cam)
                    object.__setattr__(self, '_selected_key', key)
                    break
        if object.__getattribute__(self, '_camera') is None:
            raise RuntimeError('No camera could be opened')
        if object.__getattribute__(self, '_selected_key') == 'noise' and hardware:
            logger.warning('No camera hardware detected; using simulated camera')

    def read(self) -> 'Image':
        '''Read one frame and return it as a numpy array.'''
        self._ensure_open()
        camera = object.__getattribute__(self, '_camera')
        ok, frame = camera.saferead()
        if not ok or frame is None:
            raise RuntimeError('Camera read failed')
        return frame

    def __getattr__(self, name: str):
        self._ensure_open()
        return getattr(object.__getattribute__(self, '_camera'), name)

    def __setattr__(self, name: str, value) -> None:
        self._ensure_open()
        setattr(object.__getattribute__(self, '_camera'), name, value)

    def __repr__(self) -> str:
        key = object.__getattribute__(self, '_selected_key')
        label = _BACKENDS[key].label if key else 'uninitialized'
        return f'<Camera: {label}>'

    def live_view(self, fps: float = 30.0) -> '_LiveView':
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
        _LiveView
            Handle for the running feed.  Call :meth:`_LiveView.stop`
            to end it.

        Raises
        ------
        ImportError
            If :mod:`ipywidgets` is not installed.

        Notes
        -----
        Keep a reference to the returned handle — if it is
        garbage-collected the update loop may stop::

            live = camera.live_view()
            live.stop()   # when done

        Examples
        --------
        ::

            camera = Camera()
            live = camera.live_view()
            # ...
            live.stop()
        '''
        try:
            import ipywidgets as widgets
            from IPython.display import display
        except ImportError as ex:
            raise ImportError(
                'ipywidgets is required for live_view(). '
                'Install it with: pip install ipywidgets'
            ) from ex

        import asyncio
        import cv2

        self._ensure_open()
        frame = self.read()

        def _encode(f):
            _, buf = cv2.imencode('.jpg', f)
            return bytes(buf)

        widget = widgets.Image(
            value=_encode(frame),
            format='jpeg',
            width=frame.shape[1],
            height=frame.shape[0],
        )
        display(widget)

        async def _loop():
            interval = 1.0 / fps
            while True:
                try:
                    widget.value = _encode(self.read())
                except Exception:
                    break
                await asyncio.sleep(interval)

        return _LiveView(asyncio.ensure_future(_loop()))

    def controls(self):
        '''Return an interactive property panel for use in Jupyter.

        Creates a :class:`~QVideo.lib._jupyter.CameraControls` widget that
        exposes all registered camera properties as editable inputs.
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
        try:
            from QVideo.lib._jupyter import CameraControls
        except ImportError as ex:
            raise ImportError(
                'ipywidgets is required for camera.controls(). '
                'Install it with: pip install ipywidgets'
            ) from ex
        return CameraControls(object.__getattribute__(self, '_camera'))

    def __await__(self):
        return self._select().__await__()

    async def _select(self) -> '_CameraProxy':
        candidates = object.__getattribute__(self, '_candidates')
        if len(candidates) > 1:
            try:
                from IPython import get_ipython
                if get_ipython() is not None:
                    working = _working_candidates(candidates)
                    if working:
                        _jupyter_report(working)
                        object.__setattr__(self, '_candidates', [working[0]])
            except ImportError:
                pass
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
        If *model* is not a recognised backend name.

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
    candidates = _discover(model, cameraID)
    if not candidates:
        raise RuntimeError(
            'No camera available'
            + (f' for model {model!r}' if model else '')
        )
    return _CameraProxy(candidates)
