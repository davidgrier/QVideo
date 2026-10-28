'''Notebook and script front door: ``Camera()`` and ``Filter()``.

``Camera()`` finds a camera and returns something that reads frames
without any window; in a notebook it also shows live video and controls.
``Filter()`` lists the filters and builds them by name.  See the chapter
"Using QVideo in Jupyter" of the documentation.

Modules
-------
camera
    The ``Camera()`` factory, the proxy that it returns and
    ``available_cameras()``.
filter
    The ``Filter()`` factory.
widgets
    The :mod:`ipywidgets` front end (controls, live view, chooser), the
    only module that imports ``ipywidgets``.
'''
from .camera import Camera, available_cameras
from .filter import Filter


__all__ = 'Camera Filter available_cameras'.split()
