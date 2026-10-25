Architecture
============

QVideo is organized into four layers.  Each layer depends only on the
layers below it, so individual components can be used in isolation.

.. code-block:: text

   ┌──────────────────────────────────────────────────┐
   │  QCamcorder  Demo  FilterDemo  ROIDemo           │  application layer
   │  TrackpyDemo  YoloDemo  CompositeDemo            │
   ├──────────────┬───────────────────────────────────┤
   │  QCameraTree │  QVideoScreen  QFilterRack  DVR   │  UI layer
   ├──────────────┴───────────────────────────────────┤
   │  QVideoSource  (QThread)                         │  threading layer
   ├──────────────────────────────────────────────────┤
   │  QCamera  (hardware abstraction)                 │  camera layer
   └──────────────────────────────────────────────────┘

Camera layer — ``QVideo.lib.QCamera``
--------------------------------------

:class:`~QVideo.lib.QCamera.QCamera` is the abstract base for all cameras.
Subclasses implement three methods:

* ``_initialize() -> bool`` — open the device, call
  :meth:`~QVideo.lib.QCamera.QCamera.registerProperty` /
  :meth:`~QVideo.lib.QCamera.QCamera.registerMethod` for every adjustable
  parameter, return success.
* ``_deinitialize()`` — release the device.
* ``read() -> (bool, ndarray | None)`` — capture one frame.

:meth:`~QVideo.lib.QCamera.QCamera.registerProperty` stores a property
spec in ``self._properties``.  :meth:`~QVideo.lib.QCamera.QCamera.get`,
:meth:`~QVideo.lib.QCamera.QCamera.set`, and
:meth:`~QVideo.lib.QCamera.QCamera.execute` all route through this dict
through this dict.  Attribute access (``camera.fps``) delegates to
registered getters via ``__getattr__``, so subclasses need no explicit
Python properties for camera parameters.

One reentrant lock serializes all access to the device.
``registerProperty`` and ``registerMethod`` wrap every getter, setter and
method in it, and ``saferead`` holds it for each frame, so no property is
read or written while a frame is being read and a multi-step change (stop
acquisition, set, restart) is never interleaved with anything else.
Neither backends nor the code above them lock anything themselves: a GUI
that needs to poll the hardware asks the camera for a snapshot
(``QGenicamCamera.state``), which the camera reads under the lock.

Threading layer — ``QVideo.lib.QVideoSource``
----------------------------------------------

:class:`~QVideo.lib.QVideoSource.QVideoSource` wraps a camera in a
``QThread``, calling ``camera.saferead()`` in a loop and emitting
``newFrame(ndarray, FrameInfo)``.  :class:`~QVideo.lib.videotypes.FrameInfo`
carries the frame's index and a capture timestamp taken in the capture
thread immediately after the camera returns the frame; slots that need
only the image may accept a single argument.  It is the standard way to
drive a camera from the GUI thread.

Frame delivery
--------------

A source emits every frame it captures.  What happens when a consumer
cannot keep up is that consumer's policy, and each consumer states its
own:

========================  ==================================================
Policy                    Behavior when the consumer falls behind
========================  ==================================================
Guaranteed                No frame is dropped.  Frames queue in memory and
                          the consumer reports that it is behind.
Soft                      Frames are time-stamped; analysis tolerates gaps
                          because it can see them.
Latest                    Only the newest waiting frame is kept; the rest
                          are dropped and counted.
Display only              As for latest; nothing downstream depends on it.
========================  ==================================================

The recorders (:class:`~QVideo.lib.QVideoWriter.QVideoWriter`) are
guaranteed.  Their queue is unbounded, so the code that owns a recording
watches it.  ``QDVRWidget`` compares the capture time of each frame the
camera delivers (:class:`~QVideo.lib.videotypes.FrameInfo`) with that of
the newest frame the writer has taken up.  The difference is the backlog,
and it is measured even while the writer is stuck inside one write.  When
it exceeds ``lagLimit`` (one second by default) the widget emits
``behind(lag)`` once, and again after the writer has caught up and fallen
behind anew.  By default it then stops the recording
(``stopWhenBehind=True``) after logging the reason and emitting
``stopped(reason)``, so a slow disk cannot fill memory.  An application
that prefers to record through the backlog sets ``stopWhenBehind=False``,
raises ``lagLimit``, or both.

Stopping a recording never discards captured frames: the widget stops
sending new ones, and the writer finishes those already waiting before it
closes the file and ends its thread.

:class:`~QVideo.lib.QFilterStack.QFilterStack` and
:class:`~QVideo.lib.QVideoScreen.QVideoScreen` are latest-wins.  The stack
keeps ``depth`` waiting frames (one by default) and reports its drops with
``framesDropped``; the screen shows at most one frame per throttle
interval.  The detection overlays (trackpy, YOLO) run one frame at a time
on a worker and skip the frames that arrive meanwhile.  Interactive
overlays, which draw graphics and respond to the user in the GUI thread,
have no worker and no policy to choose.

UI layer
--------

:class:`~QVideo.lib.QCameraTree.QCameraTree` is a
``pyqtgraph.ParameterTree`` widget that reads ``camera._properties`` to
auto-build a control panel — no manual UI code is needed per camera.

:class:`~QVideo.lib.QVideoScreen.QVideoScreen` displays live frames from
a :class:`~QVideo.lib.QVideoSource.QVideoSource`.  It maintains the
video aspect ratio by resizing its containing window whenever the frame
dimensions change.  After each displayed frame it emits ``newFrame``
carrying either the video frame or, when
:attr:`~QVideo.lib.QVideoScreen.QVideoScreen.composite` is enabled, the
rendered scene (video + overlays) as an RGBA array.  Its
:attr:`~QVideo.lib.QVideoScreen.QVideoScreen.fps` property reports the
effective display rate, so the screen can be used directly as a DVR
source for composite recording.  Setting
:attr:`~QVideo.lib.QVideoScreen.QVideoScreen.colormap` applies a
false-color LUT to grayscale frames at display time without affecting
the underlying frame data.

:class:`~QVideo.lib.QFilterStack.QFilterStack` runs
:class:`~QVideo.lib.QVideoFilter.VideoFilter` objects on a worker thread
between a source and its consumers (a screen, a recorder, an overlay), so
every consumer sees the same filtered stream and a slow filter never makes
the interface unresponsive.  A
:class:`~QVideo.lib.QFilterRack.QFilterRack` lets the user add, remove,
reorder, and adjust the filters while the program runs.

Application layer
-----------------

:class:`~QVideo.QCamcorder.QCamcorder` composes a
:class:`~QVideo.lib.QVideoScreen.QVideoScreen`,
:class:`~QVideo.lib.QCameraTree.QCameraTree`, and
:class:`~QVideo.dvr.QDVRWidget.QDVRWidget` into a single reusable widget.

The :mod:`~QVideo.demos` package provides ready-to-run applications
built on the framework, following two inheritance chains:

* :class:`~QVideo.demos.demo.Demo` — minimal layout: screen + camera tree.
  :class:`~QVideo.demos.filterdemo.FilterDemo` extends it with a
  :class:`~QVideo.lib.QFilterRack.QFilterRack` panel and a
  :class:`~QVideo.lib.QFilterStack.QFilterStack`.
  :class:`~QVideo.demos.trackpydemo.TrackpyDemo` extends it with a
  :class:`~QVideo.overlays.trackpy.QTrackpyWidget` panel and live particle
  markers.
  :class:`~QVideo.demos.yolodemo.YoloDemo` extends it with a
  :class:`~QVideo.overlays.yolo.QYoloWidget` panel and live YOLO
  detection bounding boxes.
* :class:`~QVideo.demos.ROIdemo.ROIDemo` extends
  :class:`~QVideo.QCamcorder.QCamcorder` with a draggable ROI overlay.
  :class:`~QVideo.demos.compositedemo.CompositeDemo` extends it with a
  :class:`~QVideo.overlays.trackpy.QTrackpyWidget` panel and a
  ``Composite`` checkbox that switches the DVR between recording raw
  frames and recording the rendered scene (video + overlay markers).

Camera backends
---------------

Each backend lives in ``cameras/<Name>/`` and follows the pattern:

* ``Q<Name>Camera`` — subclasses :class:`~QVideo.lib.QCamera.QCamera`.
* ``Q<Name>Source`` — subclasses
  :class:`~QVideo.lib.QVideoSource.QVideoSource`.
* ``Q<Name>Tree`` — subclasses
  :class:`~QVideo.lib.QCameraTree.QCameraTree` when extra UI logic is
  needed.

:class:`~QVideo.cameras.OpenCV.QOpenCVTree.QOpenCVTree` (``-c``) probes the
connected device at startup to discover its supported resolutions and actual
maximum frame rates, then presents a ``"W×H @ N Hz"`` dropdown.  Selecting
an entry atomically updates width, height, and frame rate on the live device
without stopping the video source.  Width, height, and fps are shown as
read-only fields; all format changes go through the dropdown.  When probing
yields no format information the dropdown is omitted and width/height are
displayed as plain read-only values.

Hardware-specific packages are soft dependencies: the import is wrapped in
``try/except (ImportError, ModuleNotFoundError)``.

GenICam cameras (:mod:`~QVideo.cameras.Genicam`,
:mod:`~QVideo.cameras.Flir`, :mod:`~QVideo.cameras.Vimbax`) discover their
GenTL producer ``.cti`` file at runtime via the ``GENICAM_GENTL64_PATH``
environment variable set by the manufacturer's SDK installer.

:mod:`~QVideo.cameras.Noise` is the reference implementation — no hardware
required, used as a model for tests and for verifying the framework.
