'''The ``Q<Name>Source`` classes of the backends, which are retired.

Each was a ``QVideoSource`` that opened its camera, and
``QVideoSource(camera)`` does the same for every backend.  A package
keeps the old names working until the next major release: its
``__getattr__`` hands out a function that warns and returns the source.
'''
from __future__ import annotations

import warnings
from collections.abc import Callable

from QVideo.lib import QCamera, QVideoSource


__all__ = ['deprecated_sources']


def deprecated_sources(package: str,
                       **cameras: type[QCamera]) -> Callable[[str], object]:
    '''Return the ``__getattr__`` of *package* for its retired sources.

    Parameters
    ----------
    package : str
        Name of the package, for the messages.
    **cameras :
        Each retired name and the camera class that its source wrapped.
    '''
    def __getattr__(name: str):
        camera_class = cameras.get(name)
        if camera_class is None:
            raise AttributeError(
                f'module {package!r} has no attribute {name!r}')

        def source(*args, **kwargs) -> QVideoSource:
            warnings.warn(
                f'{name} is deprecated and will be removed in the next '
                f'major release; use QVideoSource({camera_class.__name__}'
                '(...)) instead', DeprecationWarning, stacklevel=2)
            camera = kwargs.pop('camera', None)
            if args and isinstance(args[0], QCamera):
                camera, args = args[0], args[1:]
            if camera is None:
                camera = camera_class(*args, **kwargs)
            return QVideoSource(camera)

        source.__name__ = name
        return source

    return __getattr__
