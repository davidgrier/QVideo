'''Registry of the camera backends that QVideo knows.

``Camera()``, the command-line chooser and the documentation all use this
table.  A new backend adds an entry to ``_BACKENDS``, with the flag and
the help text that select it on the command line, and its key to
``_DISCOVERY_ORDER``.
'''
import importlib
from typing import NamedTuple


class _BackendEntry(NamedTuple):
    module: str
    camera_cls: str
    tree_cls: str
    label: str
    flag: str = ''
    help: str = ''


_BACKENDS: dict[str, _BackendEntry] = {
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
        importlib.import_module(_BACKENDS[key].module)
        return True
    except (ImportError, ModuleNotFoundError):
        return False


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
