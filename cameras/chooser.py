'''Which cameras exist, how to open one, and how a command line picks it.

This module has four parts, in this order.

1. **The table of backends**: :data:`BACKENDS` says what each backend is
   called, where its classes are and which command-line flag selects it.
   The command-line flags, ``Camera()``, the remote worker and the
   documentation all read this table, so nothing else lists the backends.
2. **Finding backends**: :func:`discover` lists the backends that can be
   imported, in the order of :data:`BACKENDS`.
3. **Opening cameras**: :func:`create_camera` makes one camera,
   :func:`open_first` opens the first of several that works, and
   :func:`available_cameras` lists every camera that opens.  A backend that
   reads frames through a library that holds the interpreter lock opens in
   a process of its own (:func:`uses_worker`).
4. **The command line**: :func:`camera_parser` adds the camera flags to an
   argument parser, :func:`open_camera` opens the camera that the flags
   name, :func:`make_tree` builds its controls and :func:`choose_camera`
   does the last two in a row.

**Who calls what.**  ``lib/_launch.py`` (every demo and application) calls
:func:`open_camera` and :func:`make_tree`; ``Camera()`` in
``interactive/camera.py`` calls :func:`discover`, :func:`open_first` and
:func:`working`; :class:`~QVideo.widgets.QCameraChooser` calls
:func:`available_cameras`; the worker of a remote camera reads
:data:`BACKENDS`.

A new backend adds an entry to :data:`BACKENDS`, with the flag and the help
text that select it, in the place of its priority: ``Camera()`` tries the
backends in the order of the table, and the noise camera stays last.

**Defaults and fallbacks.**  With no flag, a program started from the command
line opens the *noise* camera (:func:`open_camera`); if the camera that a flag
names cannot be opened, it opens the noise camera instead, with a warning in
the log.  ``Camera()`` with no model tries every backend in turn, real hardware
first, and ends with the noise camera if nothing else opens; ``Camera('flir')``
has no fallback and raises ``RuntimeError`` if that camera does not open.  Read
the log before you trust a measurement: a backend whose package is missing
looks just like a working one that shows noise.

**Cameras in a process of their own.**  The GenICam backends that use
Harvesters (Basler, Flir, IDS, MV and VimbaX) read frames through a binding
that holds the interpreter lock, which freezes the other threads of the
program.  :func:`create_camera` therefore opens them in a worker process
(:class:`~QVideo.lib.remote.camera.QRemoteCamera`) on macOS and Linux,
whatever the caller, and there is no flag for it.  Creating the camera class
yourself (``QFlirCamera()``) keeps it in the program.  On Windows, where the
worker is not available, these backends open in the program.
'''
import contextlib
import importlib
import logging
import sys
from argparse import SUPPRESS, ArgumentParser, Namespace
from collections.abc import Iterator
from importlib.metadata import PackageNotFoundError, version
from typing import NamedTuple

from QVideo.lib import QCamera, QCameraTree
from QVideo.lib._qapp import ensure_qapp

__all__ = ['BACKENDS', 'LOG_LEVELS', 'available_cameras', 'camera_class',
           'camera_parser', 'choose_camera', 'create_camera', 'discover',
           'make_tree', 'open_camera', 'open_first', 'tree_class',
           'uses_worker', 'working']

logger = logging.getLogger(__name__)

#: A candidate camera: the key of a backend and the ID of the camera.
Candidate = tuple[str, int]

#: Why a backend could not open: its label and the exception or text.
Failure = tuple[str, object]


# ----------------------------------------------------------------------
# The table of backends
# ----------------------------------------------------------------------

class _BackendEntry(NamedTuple):

    '''One row of :data:`BACKENDS`.

    Attributes
    ----------
    module : str
        The package of the backend, imported to find its classes.
    camera_cls, tree_cls : str
        Names of the camera class and of the class of its controls in
        *module*.
    label : str
        Name for people: the log, the chooser and the list of cameras.
    flag : str
        The command-line flag that selects the backend (``'-f'``).  An
        empty flag means that the command line cannot select it (the noise
        camera, which is the default).
    help : str
        The help text of *flag*.
    worker : bool
        The backend reads frames through a library that holds the
        interpreter lock (the ``genicam`` binding of Harvesters), so the
        camera opens in a process of its own where that is available.
    '''

    module: str
    camera_cls: str
    tree_cls: str
    label: str
    flag: str = ''
    help: str = ''
    worker: bool = False


#: The backends, by key, in the order that ``Camera()`` tries them when it
#: is not told which one to use: real hardware first, the simulated camera
#: last.  The key is the lowercase name that ``Camera()`` accepts and that
#: the worker of a remote camera is started with.
BACKENDS: dict[str, _BackendEntry] = {
    'basler': _BackendEntry(
        'QVideo.cameras.Basler', 'QBaslerCamera', 'QBaslerTree', 'Basler',
        '-b', 'Basler pylon camera', worker=True),
    'flir': _BackendEntry(
        'QVideo.cameras.Flir', 'QFlirCamera', 'QFlirTree', 'Flir',
        '-f', 'Flir camera', worker=True),
    'ids': _BackendEntry(
        'QVideo.cameras.IDS', 'QIDSCamera', 'QIDSTree', 'IDS',
        '-i', 'IDS Imaging camera', worker=True),
    'mv': _BackendEntry(
        'QVideo.cameras.MV', 'QMVCamera', 'QMVTree', 'MV',
        '-m', 'MATRIX VISION mvGenTLProducer (universal GenICam)',
        worker=True),
    'vimbax': _BackendEntry(
        'QVideo.cameras.Vimbax', 'QVimbaXCamera', 'QVimbaXTree', 'VimbaX',
        '-v', 'Allied Vision VimbaX camera', worker=True),
    'viva': _BackendEntry(
        'QVideo.cameras.Viva', 'QVivaCamera', 'QVivaTree', 'Viva',
        '-g', 'GenICam camera via viva-genicam (preferred; no vendor SDK)'),
    'picamera': _BackendEntry(
        'QVideo.cameras.Picamera', 'QPicamera', 'QPicameraTree', 'Picamera',
        '-p', 'Raspberry Pi camera module'),
    'opencv': _BackendEntry(
        'QVideo.cameras.OpenCV', 'QOpenCVCamera', 'QOpenCVTree', 'OpenCV',
        '-c', 'OpenCV camera'),
    'noise': _BackendEntry(
        'QVideo.cameras.Noise', 'QNoiseCamera', 'QNoiseTree', 'Noise'),
}

#: The backends that a command-line flag selects.
_CAMERAS = {key: entry for key, entry in BACKENDS.items() if entry.flag}


# ----------------------------------------------------------------------
# Finding backends
# ----------------------------------------------------------------------

def _probe(key: str) -> bool:
    '''Return True if the package of backend *key* can be imported.

    A backend whose vendor library is not installed is skipped, not an
    error: its module catches the failed import itself, so a failure here
    means that the module does not exist or cannot be loaded at all.
    '''
    try:
        importlib.import_module(BACKENDS[key].module)
        return True
    except ImportError:
        return False


def discover(model: str | None,
             camera_id: int | str = 0) -> list[Candidate]:
    '''Return the backends to try, as ``(key, camera_id)`` pairs.

    Parameters
    ----------
    model : str or None
        The key of one backend (any case), or ``None`` for every backend in
        the order of :data:`BACKENDS`.
    camera_id : int or str
        The camera that each pair names.

    Returns
    -------
    list[tuple[str, int]]
        The pairs of the backends that can be imported.  With *model* given
        this has one pair, or none if that backend cannot be imported.

    Raises
    ------
    ValueError
        If *model* names no backend.
    '''
    if model is not None:
        key = model.lower()
        if key not in BACKENDS:
            raise ValueError(
                f'Unknown camera model {model!r}. '
                f'Available: {sorted(BACKENDS)}'
            )
        return [(key, camera_id)] if _probe(key) else []
    return [(key, camera_id) for key in BACKENDS if _probe(key)]


# ----------------------------------------------------------------------
# Opening cameras
# ----------------------------------------------------------------------

def uses_worker(key: str) -> bool:
    '''Return True if the camera of backend *key* opens in a process of its
    own.

    That is so for the backends whose library holds the interpreter lock
    (the ``worker`` field of :data:`BACKENDS`), except on Windows, where the
    worker is not available yet.
    '''
    return BACKENDS[key].worker and sys.platform != 'win32'


def _load(entry: _BackendEntry, name: str) -> type:
    '''Return the class *name* from the package of *entry*.'''
    return getattr(importlib.import_module(entry.module), name)


def camera_class(key: str) -> type[QCamera]:
    '''Return the camera class of backend *key*, importing its package.'''
    return _load(BACKENDS[key], BACKENDS[key].camera_cls)


def tree_class(key: str) -> type[QCameraTree]:
    '''Return the class of the controls of backend *key*.'''
    return _load(BACKENDS[key], BACKENDS[key].tree_cls)


def create_camera(key: str, camera_id: int | str = 0,
                  errors: list[Failure] | None = None) -> QCamera | None:
    '''Import and instantiate the camera of backend *key*.

    Parameters
    ----------
    key : str
        Key of the backend in :data:`BACKENDS`.
    camera_id : int or str
        Which camera of that backend: an index or, for a backend that
        understands it, text (a name, an identifier).
    errors : list, optional
        If given, a ``(label, exception)`` pair is appended to it when the
        camera cannot be created.

    Returns
    -------
    QCamera or None
        The camera, or ``None`` if creating it raised an exception.  The
        exception is logged as a warning and is not raised again.  The
        camera that comes back may not be open: ask ``isOpen()``.  If
        :func:`uses_worker` is true for *key* it is a
        :class:`~QVideo.lib.remote.camera.QRemoteCamera`, which looks like
        the camera of the backend.
    '''
    ensure_qapp()
    entry = BACKENDS[key]
    try:
        if uses_worker(key):
            from QVideo.lib.remote import QRemoteCamera
            camera_class(key).precheck()
            return QRemoteCamera(key, cameraID=camera_id)
        return camera_class(key)(cameraID=camera_id)
    except Exception as ex:
        logger.warning(f'Could not open {entry.label}: {ex}')
        logger.debug(f'Where {entry.label} failed to open:', exc_info=True)
        if errors is not None:
            errors.append((entry.label, ex))
        return None


@contextlib.contextmanager
def quiet() -> Iterator[None]:
    '''Suppress sub-ERROR log messages from QVideo loggers during probing.

    Trying several backends in turn makes the ones that fail log warnings
    that mean nothing once another opens.  Nothing is suppressed when debug
    logging is on, so that the tracebacks of failures to open a camera can
    be seen.
    '''
    root = logging.getLogger('QVideo')
    saved = root.level
    if root.getEffectiveLevel() > logging.DEBUG:
        root.setLevel(logging.ERROR)
    try:
        yield
    finally:
        root.setLevel(saved)


def describe(errors: list[Failure]) -> str:
    '''Format ``(label, reason)`` pairs, one backend per line.'''
    return '\n'.join(f'{label}: {reason}' for label, reason in errors)


def _opened(candidates: list[Candidate],
            errors: list[Failure]) -> Iterator[tuple[str, int, QCamera]]:
    '''Yield ``(key, camera_id, camera)`` for each candidate that opens.

    The candidates are tried in order and one at a time, so a caller that
    stops asking stops opening cameras.  Why a candidate did not open is
    added to *errors*.
    '''
    for key, camera_id in candidates:
        camera = create_camera(key, camera_id, errors)
        if camera is None:
            continue
        if camera.isOpen():
            yield key, camera_id, camera
        else:               # created, but the device is not open
            errors.append((BACKENDS[key].label, 'device failed to open'))


def open_first(candidates: list[Candidate]) -> tuple[str, QCamera]:
    '''Open the first of *candidates* that works.

    Each candidate is created and asked whether it is open.  A candidate
    that raises or is not open is recorded and the next is tried.  If the
    camera that opens is the simulated noise camera although real backends
    were among the candidates, the log says that no hardware was found, and
    why each backend failed.

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
    errors: list[Failure] = []
    with quiet():
        opened = next(((key, camera)
                       for key, _, camera in _opened(candidates, errors)),
                      None)
    reasons = f':\n{describe(errors)}' if errors else ''
    if opened is None:
        raise RuntimeError(f'No camera could be opened{reasons}')
    if opened[0] == 'noise' and hardware:
        logger.warning(f'No camera hardware detected; using simulated '
                       f'camera{reasons}')
    return opened


def working(candidates: list[Candidate]) -> list[Candidate]:
    '''Return only the candidates whose cameras open successfully.

    Every candidate is opened and closed again, so the light of a camera
    may blink.
    '''
    found = []
    with quiet():
        for key, camera_id, camera in _opened(candidates, []):
            camera.close()
            found.append((key, camera_id))
    return found


def available_cameras() -> list[tuple[str, int, str]]:
    '''List the cameras that can be opened.

    Each installed backend is asked for its devices and each device is
    opened and closed again to see that it works, so the light of a
    camera may blink.  The simulated Noise camera is always listed.

    Returns
    -------
    list[tuple[str, int, str]]
        ``(model, cameraID, name)`` in priority order.  The first two
        items are the arguments of
        :func:`~QVideo.interactive.camera.Camera`; *name* is the name that
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
        names = camera_class(key).deviceNames()
        ids = sorted(names) or [0]
        label = BACKENDS[key].label
        for _key, camera_id in working([(key, i) for i in ids]):
            found.append((label, camera_id, names.get(camera_id, label)))
    return found


# ----------------------------------------------------------------------
# The command line
# ----------------------------------------------------------------------

#: The values of ``--log-level``, from most to least talkative.
LOG_LEVELS = ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')


def _version() -> str:
    '''Return the version of the installed QVideo, or ``'unknown'``.'''
    try:
        return version('QVideo')
    except PackageNotFoundError:  # a bare source checkout
        return 'unknown'


def camera_parser(parser: ArgumentParser | None = None) -> ArgumentParser:
    '''Add the camera options to an argument parser.

    Adds, to *parser* or to a new one, a group of mutually exclusive
    camera flags (one for every backend of :data:`BACKENDS` that has a
    flag: ``python QCamcorder.py --help`` lists them), an optional
    positional ``cameraID``, ``--version`` and ``--log-level``.  An option
    that the parser has already is left as it is.

    Parameters
    ----------
    parser : ArgumentParser or None
        The parser to extend.  If ``None``, a new one is created.

    Returns
    -------
    ArgumentParser
        The parser, with these options added:

        one flag for each backend that has one
            Selects the backend (the flags are in :data:`BACKENDS`); at
            most one.
        ``cameraID``
            Which camera of the backend: an index, or text (part of the
            name of the device) for a backend that lists names.  Without
            it the first camera opens, unless the backend lists several:
            :func:`~QVideo.lib.launch` then asks which one.
        ``--version``
            Prints the version of QVideo and ends the program.
        ``--log-level``
            One of :data:`LOG_LEVELS`, in either case.  The attribute
            ``log_level`` is absent if the option is not given, so that
            a program that configures logging itself is left alone;
            :func:`~QVideo.lib.launch` applies it.
    '''
    parser = parser or ArgumentParser()
    # An option that the parser has already has a default that is not None.
    camera = parser.add_argument_group(
        'camera selection', 'At most one flag; with none, a simulated '
        'camera runs.')
    if parser.get_default(next(iter(_CAMERAS))) is None:
        group = camera.add_mutually_exclusive_group()
        for dest, entry in _CAMERAS.items():
            group.add_argument(entry.flag, dest=dest, help=entry.help,
                               action='store_true')
    if not any(a.dest == 'cameraID' for a in parser._actions):
        camera.add_argument('cameraID', nargs='?', type=_spec,
                            help='which camera of the backend: an index, '
                            'or part of the name of the device (default: '
                            'the only camera, or a choice from a list)')
    general = parser.add_argument_group('general')
    if parser.get_default('log_level') is None:
        general.add_argument('--log-level', dest='log_level',
                             type=str.upper, choices=LOG_LEVELS,
                             default=SUPPRESS, metavar='LEVEL',
                             help='show log messages of this level and '
                             'above: ' + ', '.join(LOG_LEVELS)
                             + ' (default: WARNING)')
    if '--version' not in parser._option_string_actions:
        general.add_argument('--version', action='version',
                             version=f'QVideo {_version()}')
    return parser


def _spec(text: str) -> int | str:
    '''Return *text* as an index if it is all digits, else as it is.'''
    return int(text) if text.isdigit() else text


def _model(args: Namespace) -> str:
    '''Return the key of the backend that the flags in *args* select.'''
    return next((dest for dest in _CAMERAS if getattr(args, dest, False)),
                'noise')


def _devices(key: str, spec: int | str | None) -> dict[int, str]:
    '''Return the devices of backend *key* that *spec* could mean.'''
    names = camera_class(key).deviceNames()
    if isinstance(spec, str):
        text = spec.lower()
        names = {i: n for i, n in names.items() if text in n.lower()}
    return names


def choices(model: str, spec: int | str | None) -> dict[int, str]:
    '''Return the cameras to choose from, when the command line is vague.

    Parameters
    ----------
    model : str
        Key of the backend.
    spec : int, str or None
        The ``cameraID`` of the command line.

    Returns
    -------
    dict[int, str]
        ``{cameraID: name}`` of the devices that match *spec* if there are
        several of them (no *spec* matches all), else ``{}``: an index, a
        simulated camera, and a backend that lists no names never need to
        ask.
    '''
    if model == 'noise' or isinstance(spec, int):
        return {}
    names = _devices(model, spec)
    return names if len(names) > 1 else {}


def resolve(model: str, spec: int | str | None) -> int | str:
    '''Return the *cameraID* that *spec* names.

    A name that fits one device becomes its index.  Text that fits none
    (an identifier, a file, an address) is left for the camera to
    interpret, and no *spec* means the first camera.
    '''
    if spec is None:
        return 0
    if isinstance(spec, int):
        return spec
    names = _devices(model, spec)
    return next(iter(names)) if len(names) == 1 else spec


def open_camera(parser: ArgumentParser | None = None,
                cameraID: int | str | None = None
                ) -> tuple[str, QCamera]:
    '''Open the camera that the command-line arguments name.

    The backend is the one whose flag is on the command line, or the
    simulated *noise* camera if there is none.  If the camera that was
    asked for cannot be opened the noise camera is opened instead, with a
    warning in the log.  Unknown arguments are ignored, so that the program
    can read its own.

    It builds no widget, so it may run in a thread of its own while the
    interface starts; see :func:`~QVideo.lib.launch`.

    Parameters
    ----------
    parser : ArgumentParser or None
        The parser that reads the command line.  The camera options are
        added to it.  If ``None``, a new one is created.
    cameraID : int, str or None
        The camera, in place of the one on the command line (for a program
        that has asked the user).

    Returns
    -------
    tuple
        The key of the backend (as in :data:`BACKENDS`) and the open
        camera.
    '''
    args, _ = camera_parser(parser).parse_known_args()
    model = _model(args)
    spec = resolve(model, args.cameraID if cameraID is None else cameraID)
    try:
        return open_first(discover(model, spec))
    except RuntimeError as ex:
        logger.warning(str(ex))
        return open_first(discover('noise', spec))


def make_tree(key: str, camera: QCamera) -> QCameraTree:
    '''Return the camera tree widget for an open *camera*.

    This creates a widget, so call it in the thread of the interface.

    Parameters
    ----------
    key : str
        Key of the backend that opened the camera.
    camera : QCamera
        The open camera.

    Returns
    -------
    QCameraTree
        An instance of the tree class of the backend, for *camera*.
    '''
    return tree_class(key)(camera=camera)


def choose_camera(parser: ArgumentParser | None = None) -> QCameraTree:
    '''Choose a camera from the command line and return its tree.

    Opens the camera with :func:`open_camera` and builds its tree with
    :func:`make_tree`, in the calling thread.

    Parameters
    ----------
    parser : ArgumentParser or None
        The parser that reads the command line, as in :func:`open_camera`.

    Returns
    -------
    QCameraTree
        The tree of the camera that was chosen.
    '''
    return make_tree(*open_camera(parser))


if __name__ == '__main__':  # pragma: no cover
    choose_camera().show()
