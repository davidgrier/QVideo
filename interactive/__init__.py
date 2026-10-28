'''Notebook and script front door: ``Camera()`` and ``Filter()``.

``Camera()`` finds a camera and returns something that reads frames
without any window; in a notebook it also shows live video and controls.
``Filter()`` lists the filters and builds them by name.  See the chapter
"Using QVideo in Jupyter" of the documentation.

Modules
-------
camera
    The ``Camera()`` factory and the proxy that it returns.
filter
    The ``Filter()`` factory.
widgets
    The :mod:`ipywidgets` front end (controls, live view, chooser), the
    only module that imports ``ipywidgets``.
'''
from .camera import Camera
from .filter import Filter


__all__ = 'Camera Filter'.split()
