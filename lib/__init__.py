'''Core abstractions for the QVideo camera framework.

Provides the base classes, threading infrastructure, and UI widgets
that all camera backends build upon.

Classes
-------
QCamera
    Abstract base class for all camera backends.
QVideoSource
    Thread that reads frames from a :class:`QCamera` and emits them.
QCameraTree
    :class:`~pyqtgraph.parametertree.ParameterTree` widget auto-built
    from a camera's registered properties.
QVideoScreen
    Widget that displays frames emitted by a :class:`QVideoSource`.
VideoFilter
    Base class for composable image-processing filters.
QVideoFilter
    Qt widget wrapper around a :class:`VideoFilter`.
QFilterBank
    Fixed, programmatically-configured pipeline of :class:`VideoFilter` instances.
QFilterRack
    Dynamic, user-reorderable pipeline of :class:`QVideoFilter` widgets.
QVideoReader
    Abstract base class for video file readers.
QVideoWriter
    Abstract base class for video file writers.
QFPSMeter
    Frame-rate measurement utility.
QListCameras
    Widget listing available camera backends.
'''
from .videotypes import Image
from .clickable import clickable
from .QCamera import QCamera
from .QVideoSource import QVideoSource
from .QCameraTree import QCameraTree
from .QVideoScreen import QVideoScreen
from .QFilterBank import QFilterBank
from .QFilterRack import QFilterRack
from .QVideoFilter import VideoFilter, QVideoFilter
from .QVideoReader import QVideoReader
from .QVideoWriter import QVideoWriter
from .chooser import choose_camera
from .QListCameras import QListCameras
from .QFPSMeter import QFPSMeter

__all__ = '''Image
clickable choose_camera QListCameras
QCamera QVideoSource QCameraTree QFilterBank QFilterRack
QVideoReader QVideoWriter QVideoScreen
QFPSMeter VideoFilter QVideoFilter'''.split()
