'''Command-line camera selection utility for QVideo applications.'''
import importlib
import logging
from argparse import ArgumentParser
from typing import NamedTuple

from QVideo.lib import QCameraTree
from ._camera import Camera, _BACKENDS

__all__ = ['camera_parser', 'choose_camera']

logger = logging.getLogger(__name__)


class _CameraEntry(NamedTuple):
    flag: str
    help: str


_CAMERAS: dict[str, _CameraEntry] = {
    'opencv':   _CameraEntry('-c', 'OpenCV camera'),
    'basler':   _CameraEntry('-b', 'Basler pylon camera'),
    'flir':     _CameraEntry('-f', 'Flir camera'),
    'ids':      _CameraEntry('-i', 'IDS Imaging camera'),
    'mv':       _CameraEntry('-m', 'MATRIX VISION mvGenTLProducer (universal GenICam)'),
    'vimbax':   _CameraEntry('-v', 'Allied Vision VimbaX camera'),
    'picamera': _CameraEntry('-p', 'Raspberry Pi camera module'),
}


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
    registered = parser._option_string_actions
    first_flag = next(iter(_CAMERAS.values())).flag
    if first_flag not in registered:
        group = parser.add_mutually_exclusive_group()
        for dest, entry in _CAMERAS.items():
            group.add_argument(entry.flag, dest=dest, help=entry.help,
                               action='store_true')
    if not any(a.dest == 'cameraID' for a in parser._actions):
        parser.add_argument('cameraID', nargs='?', type=int, default=0,
                            help='camera ID number (default: %(default)d)')
    return parser


def choose_camera(parser: ArgumentParser | None = None) -> QCameraTree:
    '''Chooses and returns a camera tree based on command-line arguments.

    Tries to import and instantiate the camera backend selected by the
    command-line flags.  Falls back to :class:`QNoiseTree` if the
    requested backend cannot be imported or instantiated.

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
    args, _ = camera_parser(parser).parse_known_args()
    model = 'noise'
    for dest in _CAMERAS:
        if getattr(args, dest, False):
            model = dest
            break

    try:
        proxy = Camera(model, args.cameraID)
        proxy._ensure_open()
    except (RuntimeError, ValueError) as ex:
        logger.warning(str(ex))
        proxy = Camera('noise', args.cameraID)
        proxy._ensure_open()

    key = object.__getattribute__(proxy, '_selected_key')
    backend = _BACKENDS[key]
    module = importlib.import_module(backend.module)
    tree_cls = getattr(module, backend.tree_cls)
    camera = object.__getattribute__(proxy, '_camera')
    return tree_cls(camera=camera)


if __name__ == '__main__':  # pragma: no cover
    choose_camera().show()
