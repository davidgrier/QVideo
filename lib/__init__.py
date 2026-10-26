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
QFrameRelay
    Latest-frame handoff from a capture thread to a GUI-thread consumer.
QVideoFilter
    Qt widget wrapper around a :class:`VideoFilter`.
QFilterRackWidget
    Dynamic, user-reorderable pipeline of :class:`QVideoFilter` widgets.
QFilterPipeline
    Worker thread that applies a pipeline of filters (or a rack) to a source.
QFilterRack
    A filter rack that owns a :class:`QFilterPipeline` for a live source.
QVideoReader
    Abstract base class for video file readers.
QVideoWriter
    Abstract base class for video file writers.
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
from .QFilterRackWidget import QFilterRackWidget
from .QFilterPipeline import QFilterPipeline
from .QFilterRack import QFilterRack
from .QFrameRelay import QFrameRelay
from .QVideoFilter import VideoFilter, QVideoFilter
from .QVideoReader import QVideoReader
from .QVideoWriter import QVideoWriter
from ._camera import Camera
from .chooser import choose_camera
from ._launch import launch
from .QListCameras import QListCameras
from .QHistogramWidget import QHistogramWidget
from .QUniformityWidget import QUniformityWidget
from .QSnapshot import QSnapshot

__all__ = '''Image
           FrameInfo
clickable Camera choose_camera launch QListCameras
QCamera QCameraError QDriverError QDeviceError QVideoSource QCameraTree
QFilterRackWidget QFilterPipeline QFilterRack QFrameRelay
QVideoReader QVideoWriter QVideoScreen
QHistogramWidget QUniformityWidget QSnapshot
VideoFilter QVideoFilter'''.split()
