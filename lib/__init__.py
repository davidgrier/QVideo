'''Core abstractions for the QVideo camera framework.

Provides the base classes, threading infrastructure, and UI widgets
that all camera backends build upon.

Classes
-------
QCamera
    Abstract base class for all camera backends.
PropertySpec
    What a camera says about one of its properties (getter, setter, type
    and limits).
QCameraError
    Base class for failures to open a camera (see also
    ``QDriverError`` and ``QDeviceError``).
QVideoSource
    Thread that reads frames from a :class:`QCamera` and emits them.
QRemoteCamera
    A :class:`QCamera` that runs in a process of its own, so that the
    library of a vendor cannot freeze the program.
QCameraOpener
    Thread that opens the camera that the command line names, so that a
    program can start the rest of its interface meanwhile.
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
ReferenceFilter
    Filter that corrects frames with a reference that it captured.
QReferenceFilter
    Widget of a :class:`ReferenceFilter`, with its capture controls.
QOverlayWidget
    Control widget of an overlay that analyzes frames on a thread.
QFilterRack
    Dynamic, user-reorderable rack of :class:`QVideoFilter` widgets that
    filters a source on a worker thread.
QFilterPipeline
    Worker thread that applies a pipeline of filters (or a rack) to a source.
    A filter rack that owns a :class:`QFilterPipeline` for a live source.
QVideoReader
    Abstract base class for video file readers.
QVideoWriter
    Abstract base class for video file writers.
QSnapshot
    Hotkey-triggered still-frame capture from any ``newFrame`` signal.
QImageSaver
    Saves any image to a file, with a timestamped default name and a report.
'''
from .videotypes import Image, FrameInfo
from .clickable import clickable
from .QCamera import QCamera, PropertySpec
from .errors import QCameraError, QDriverError, QDeviceError
from .QVideoSource import QVideoSource
from .remote import QRemoteCamera
from .QCameraTree import QCameraTree
from .QVideoScreen import QVideoScreen
from .QFilterPipeline import QFilterPipeline
from .QFilterRack import QFilterRack
from .QFrameRelay import QFrameRelay
from .QVideoFilter import VideoFilter, QVideoFilter
from .QReferenceFilter import ReferenceFilter, QReferenceFilter
from .QOverlayWidget import QOverlayWidget
from .QVideoReader import QVideoReader
from .QVideoWriter import QVideoWriter
from .QCameraOpener import QCameraOpener
from ._launch import launch
from .QImageSaver import QImageSaver
from .QSnapshot import QSnapshot

__all__ = [
    'Image', 'FrameInfo',
    'clickable', 'launch',
    'QCamera', 'PropertySpec', 'QCameraError', 'QDriverError', 'QDeviceError',
    'QVideoSource', 'QCameraTree', 'QRemoteCamera', 'QCameraOpener',
    'QFilterRack', 'QFilterPipeline', 'QFrameRelay',
    'QVideoReader', 'QVideoWriter', 'QVideoScreen',
    'QSnapshot', 'QImageSaver',
    'VideoFilter', 'QVideoFilter', 'ReferenceFilter', 'QReferenceFilter',
    'QOverlayWidget',
]
