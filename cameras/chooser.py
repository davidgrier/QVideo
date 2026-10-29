'''Which cameras exist, how to open one, and how a command line picks it.

The table of backends comes first; ``Camera()``, the command-line flags and
the documentation all use it.  A new backend adds an entry to
``BACKENDS``, with the flag and the help text that select it on the
command line, and its key to ``_DISCOVERY_ORDER``.  Next is the code that
opens a camera from the table, and last the chooser that turns the flags
of a command line into an open camera and its controls.
'''
import contextlib
import importlib
import logging
from argparse import ArgumentParser
from typing import NamedTuple

from QVideo.lib import QCamera, QCameraTree

__all__ = ['available_cameras', 'camera_parser', 'choose_camera', 'make_tree',
           'open_camera']

logger = logging.getLogger(__name__)


class _BackendEntry(NamedTuple):
    module: str
    camera_cls: str
    tree_cls: str
    label: str
    flag: str = ''
    help: str = ''


BACKENDS: dict[str, _BackendEntry] = {
    'basler': _BackendEntry(
        'QVideo.cameras.Basler', 'QBaslerCamera', 'QBaslerTree', 'Basler',
        '-b', 'Basler pylon camera'),
    'flir': _BackendEntry(
        'QVideo.cameras.Flir', 'QFlirCamera', 'QFlirTree', 'Flir',
        '-f', 'Flir camera'),
    'ids': _BackendEntry(
        'QVideo.cameras.IDS', 'QIDSCamera', 'QIDSTree', 'IDS',
        '-i', 'IDS Imaging camera'),
    'mv': _BackendEntry(
        'QVideo.cameras.MV', 'QMVCamera', 'QMVTree', 'MV',
        '-m', 'MATRIX VISION mvGenTLProducer (universal GenICam)'),
    'vimbax': _BackendEntry(
        'QVideo.cameras.Vimbax', 'QVimbaXCamera', 'QVimbaXTree', 'VimbaX',
        '-v', 'Allied Vision VimbaX camera'),
    'picamera': _BackendEntry(
        'QVideo.cameras.Picamera', 'QPicamera', 'QPicameraTree', 'Picamera',
        '-p', 'Raspberry Pi camera module'),
    'opencv': _BackendEntry(
        'QVideo.cameras.OpenCV', 'QOpenCVCamera', 'QOpenCVTree', 'OpenCV',
        '-c', 'OpenCV camera'),
    'noise': _BackendEntry(
        'QVideo.cameras.Noise', 'QNoiseCamera', 'QNoiseTree', 'Noise'),
}

_DISCOVERY_ORDER = [
    'basler', 'flir', 'ids', 'mv', 'vimbax', 'picamera', 'opencv', 'noise']


def _probe(key: str) -> bool:
    '''Return True if the backend module can be imported.'''
    try:
        importlib.import_module(BACKENDS[key].module)
        return True
    except (ImportError, ModuleNotFoundError):
        return False


def discover(model: str | None, camera_id: int = 0) -> list[tuple[str, int]]:
    '''Return (backend_key, camera_id) pairs for importable backends.'''
    if model is not None:
        key = model.lower()
        if key not in BACKENDS:
            raise ValueError(
                f'Unknown camera model {model!r}. '
                f'Available: {sorted(BACKENDS)}'
            )
        return [(key, camera_id)] if _probe(key) else []
    return [(key, camera_id) for key in _DISCOVERY_ORDER if _probe(key)]


#: The backends that a command-line flag selects.
_CAMERAS = {key: entry for key, entry in BACKENDS.items() if entry.flag}


_qapp = None  # keeps the application that ensure_qapp makes alive


def ensure_qapp() -> None:
    '''Create a QApplication if none exists (required before any QCamera).

    The application is kept in a module variable: if nothing refers to it,
    Python deletes it again as soon as this function returns.
    '''
    global _qapp
    from qtpy.QtWidgets import QApplication
    if QApplication.instance() is None:
        _qapp = QApplication([])


def create_camera(key: str, camera_id: int = 0, errors: list | None = None):
    '''Import and instantiate the camera for *key*. Returns None on failure.

    If *errors* is given, a ``(label, exception)`` pair is appended to it
    when the camera cannot be created.
    '''
    ensure_qapp()
    entry = BACKENDS[key]
    try:
        module = importlib.import_module(entry.module)
        cls = getattr(module, entry.camera_cls)
        return cls(cameraID=camera_id)
    except Exception as ex:
        logger.warning(f'Could not open {entry.label}: {ex}')
        logger.debug(f'Where {entry.label} failed to open:', exc_info=True)
        if errors is not None:
            errors.append((entry.label, ex))
        return None


@contextlib.contextmanager
def quiet():
    '''Suppress sub-ERROR log messages from QVideo loggers during probing.

    Nothing is suppressed when debug logging is on, so that the tracebacks
    of failures to open a camera can be seen.
    '''
    root = logging.getLogger('QVideo')
    saved = root.level
    if root.getEffectiveLevel() > logging.DEBUG:
        root.setLevel(logging.ERROR)
    try:
        yield
    finally:
        root.setLevel(saved)


def describe(errors: list) -> str:
    '''Format ``(label, reason)`` pairs, one backend per paragraph.'''
    return '\n'.join(f'{label}: {reason}' for label, reason in errors)


def open_first(candidates: list[tuple[str, int]]) -> tuple[str, object]:
    '''Open the first of *candidates* that works.

    Parameters
    ----------
    candidates : list of (str, int)
        Backend keys of :mod:`QVideo.cameras.chooser` and camera IDs, in
        the order to try them.

    Returns
    -------
    tuple
        The key of the backend and the open camera.

    Raises
    ------
    RuntimeError
        If no candidate opens, with the reason that each one gave.
    '''
    hardware = [key for key, _ in candidates if key != 'noise']
    errors = []
    with quiet():
        for key, camera_id in candidates:
            camera = create_camera(key, camera_id, errors)
            if camera is not None and camera.isOpen():
                break
            if camera is not None:
                errors.append((BACKENDS[key].label, 'device failed to open'))
        else:
            raise RuntimeError(
                'No camera could be opened'
                + (f':\n{describe(errors)}' if errors else ''))
    if key == 'noise' and hardware:
        logger.warning(
            'No camera hardware detected; using simulated camera'
            + (f':\n{describe(errors)}' if errors else ''))
    return key, camera


def working(
        candidates: list[tuple[str, int]]) -> list[tuple[str, int]]:
    '''Return only the candidates whose cameras open successfully.'''
    working = []
    with quiet():
        for key, camera_id in candidates:
            cam = create_camera(key, camera_id)
            if cam is not None and cam.isOpen():
                cam.close()
                working.append((key, camera_id))
    return working


def _names(key: str) -> dict[int, str]:
    '''Return the names of the devices that backend *key* can list.'''
    if key == 'opencv':
        from QVideo.cameras.OpenCV import QOpenCVDevices
        return dict(QOpenCVDevices.cameras())
    return {}


def available_cameras() -> list[tuple[str, int, str]]:
    '''List the cameras that can be opened.

    Each installed backend is asked for its devices and each device is
    opened and closed again to see that it works, so the light of a
    camera may blink.  The simulated Noise camera is always listed.

    Returns
    -------
    list[tuple[str, int, str]]
        ``(model, cameraID, name)`` in priority order.  The first two
        items are the arguments of :func:`Camera`; *name* is the name that
        the device gives itself (the model for backends that list no
        names).

    Examples
    --------
    ::

        >>> available_cameras()
        [('OpenCV', 0, 'FaceTime HD Camera'), ('Noise', 0, 'Noise')]
        >>> camera = Camera('OpenCV', 0)
    '''
    found = []
    for key, _ in discover(None):
        names = _names(key)
        ids = sorted(names) or [0]
        label = BACKENDS[key].label
        for _key, camera_id in working([(key, i) for i in ids]):
            found.append((label, camera_id, names.get(camera_id, label)))
    return found


def camera_parser(parser: ArgumentParser | None = None) -> ArgumentParser:
    '''Returns a command-line argument parser with camera selection options.

    Adds a mutually exclusive group of camera flags and an optional
    positional cameraID argument to the parser.
    If the parser already defines any of these arguments,
    they are left as-is.

    Parameters
    ----------
    parser : ArgumentParser | None
        An optional ArgumentParser to extend with camera options.
        If None, a new ArgumentParser is created.

    Returns
    -------
    ArgumentParser
        Parser with mutually exclusive flags::

            -b -> Basler (pylon)
            -c -> OpenCV
            -f -> Flir
            -i -> IDS Imaging
            -m -> MATRIX VISION mvGenTLProducer (universal GenICam)
            -p -> Raspberry Pi camera module
            -v -> Allied Vision VimbaX

        The flag can be followed by an optional positional
        cameraID argument.
    '''
    parser = parser or ArgumentParser()
    # An argument that the parser has already has a default that is not None.
    if parser.get_default(next(iter(_CAMERAS))) is None:
        group = parser.add_mutually_exclusive_group()
        for dest, entry in _CAMERAS.items():
            group.add_argument(entry.flag, dest=dest, help=entry.help,
                               action='store_true')
    if parser.get_default('cameraID') is None:
        parser.add_argument('cameraID', nargs='?', type=int, default=0,
                            help='camera ID number (default: %(default)d)')
    return parser


def open_camera(parser: ArgumentParser | None = None) -> tuple[str, QCamera]:
    '''Open the camera that the command-line arguments name.

    Tries the backend selected by the command-line flags and falls back to
    the noise camera, with a warning, if it cannot be opened.  It builds
    no widget, so it may run in a thread of its own while the interface
    starts; see :func:`~QVideo.lib.launch`.

    Parameters
    ----------
    parser : ArgumentParser | None
        An optional ArgumentParser to parse command-line arguments.
        If provided, camera options will be added to it.
        If None, a new ArgumentParser is created.

    Returns
    -------
    tuple
        The key of the backend (as in :mod:`QVideo.cameras.chooser`) and
        the open camera.
    '''
    args, _ = camera_parser(parser).parse_known_args()
    model = 'noise'
    for dest in _CAMERAS:
        if getattr(args, dest, False):
            model = dest
            break

    try:
        return open_first(discover(model, args.cameraID))
    except RuntimeError as ex:
        logger.warning(str(ex))
        return open_first(discover('noise', args.cameraID))


def make_tree(key: str, camera: QCamera) -> QCameraTree:
    '''Return the camera tree widget for an open *camera*.

    Parameters
    ----------
    key : str
        Key of the backend that opened the camera.
    camera : QCamera
        The open camera.
    '''
    backend = BACKENDS[key]
    module = importlib.import_module(backend.module)
    return getattr(module, backend.tree_cls)(camera=camera)


def choose_camera(parser: ArgumentParser | None = None) -> QCameraTree:
    '''Chooses and returns a camera tree based on command-line arguments.

    Opens the camera with :func:`open_camera` and builds its tree with
    :func:`make_tree`, in the calling thread.

    Parameters
    ----------
    parser : ArgumentParser | None
        An optional ArgumentParser to parse command-line arguments.
        If provided, camera options will be added to it.
        If None, a new ArgumentParser is created.

    Returns
    -------
    QCameraTree
        The chosen camera tree widget.
    '''
    return make_tree(*open_camera(parser))


if __name__ == '__main__':  # pragma: no cover
    choose_camera().show()
