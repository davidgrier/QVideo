'''Core abstractions for the QVideo camera framework.

Provides the base classes, threading infrastructure, and UI widgets
that all camera backends build upon.

Classes
-------
QCamera
    Abstract base class for all camera backends.
QCameraError
    Base class for failures to open a camera (see also
    ``QDriverError`` and ``QDeviceError``).
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
AsyncVideoFilter
    :class:`VideoFilter` base that runs heavy computation in a background thread.
QVideoReader
    Abstract base class for video file readers.
QVideoWriter
    Abstract base class for video file writers.
QFPSMeter
    Frame-rate measurement utility.
QSnapshot
    Hotkey-triggered still-frame capture from any ``newFrame`` signal.
QListCameras
    Widget listing available camera backends.
'''
from .videotypes import Image, FrameInfo
from .clickable import clickable
from .QCamera import QCamera
from .errors import QCameraError, QDriverError, QDeviceError
from .QVideoSource import QVideoSource
from .QCameraTree import QCameraTree
from .QVideoScreen import QVideoScreen
from .QFilterBank import QFilterBank
from .QFilterRack import QFilterRack
from .QVideoFilter import VideoFilter, QVideoFilter
from .AsyncVideoFilter import AsyncVideoFilter
from .QVideoReader import QVideoReader
from .QVideoWriter import QVideoWriter
from ._camera import Camera
from .chooser import choose_camera
from .QListCameras import QListCameras
from .QFPSMeter import QFPSMeter
from .QHistogramWidget import QHistogramWidget
from .QUniformityWidget import QUniformityWidget
from .QSnapshot import QSnapshot

__all__ = '''Image
           FrameInfo
clickable Camera choose_camera QListCameras
QCamera QCameraError QDriverError QDeviceError QVideoSource QCameraTree QFilterBank QFilterRack
QVideoReader QVideoWriter QVideoScreen
QFPSMeter QHistogramWidget QUniformityWidget QSnapshot VideoFilter QVideoFilter AsyncVideoFilter'''.split()
