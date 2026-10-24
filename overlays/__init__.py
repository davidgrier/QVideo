'''Graphical overlays for :class:`~QVideo.lib.QVideoScreen.QVideoScreen`.

Each overlay depends on its own optional packages, so the submodules are
imported on first use rather than when the package is imported.
'''
from importlib import import_module

_MODULES = {'QTrackpyOverlay': 'trackpy', 'QTrackpyWidget': 'trackpy',
            'QYoloOverlay': 'yolo', 'QYoloWidget': 'yolo'}

__all__ = list(_MODULES)


def __getattr__(name: str):
    if name not in _MODULES:
        raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
    return getattr(import_module(f'.{_MODULES[name]}', __name__), name)
