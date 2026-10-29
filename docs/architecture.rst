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
spec in ``self.properties``.  :meth:`~QVideo.lib.QCamera.QCamera.get`,
:meth:`~QVideo.lib.QCamera.QCamera.set`, and
:meth:`~QVideo.lib.QCamera.QCamera.execute` all route through this dict
through this dict.  Attribute access (``camera.fps``) delegates to
registered getters via ``__getattr__``, so subclasses need no explicit
Python properties for camera parameters.

A camera has two frame rates, as GenICam does.  ``fps`` is the rate that
was asked for, a property that can be set.
:attr:`~QVideo.lib.QCamera.QCamera.actualFps` is the rate that the camera
delivers, and it is read-only.  It equals ``fps`` unless the backend can
learn better from the hardware: a GenICam camera reports it in
``AcquisitionResultingFrameRate`` (or the node of older firmware), because
a camera delivers less than it is asked for when its exposure is long or
its buffers overrun.  :attr:`QVideoSource.fps
<QVideo.lib.QVideoSource.QVideoSource.fps>` reports ``actualFps``, so the
recorder's file header, the memory budget of the DVR, the circular buffer
and the screen all use the rate at which frames arrive.  A video file holds
one rate, the one at the start of the recording; the HDF5 format also
stores a timestamp for each frame.  Backends that report no delivered rate,
such as OpenCV, use the rate that the driver reports.  QVideo does not
measure it, because a camera that reports a rate it does not deliver is not
suitable for serious work.

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
watches it.  ``QRecorder`` compares the capture time of each frame the
camera delivers (:class:`~QVideo.lib.videotypes.FrameInfo`) with that of
the newest frame the writer has taken up.  The difference is the backlog,
and it is measured even while the writer is stuck inside one write.
``backlog(fraction)`` reports it, in steps of 5%, as a fraction of the
allowance, so an interface can warn before anything is lost.  When
it exceeds ``lagLimit`` (one second by default), or the time the camera
needs to fill ``maxMemory`` bytes (80% of the available memory by default),
the recorder emits
``behind(lag)`` once, and again after the writer has caught up and fallen
behind anew.  By default it then stops the recording
(``stopWhenBehind=True``) after logging the reason and emitting
``stopped(reason)``, so a slow disk cannot fill memory.  The reason says
what to try: install PyAV, if it is missing, or lower the frame size or
rate (for a recording to HDF5, a faster disk).  An application
that prefers to record through the backlog sets ``stopWhenBehind=False``,
raises ``lagLimit``, or both.

Stopping a recording never discards captured frames: the recorder stops
sending new ones, and the writer finishes those already waiting before it
closes the file and ends its thread.

Recording and playback do not need a window.
:class:`~QVideo.dvr.QRecorder.QRecorder` and
:class:`~QVideo.dvr.QPlayer.QPlayer` do the work, with the classes that
:mod:`~QVideo.dvr.formats` has for the extension of the file, and
:class:`~QVideo.dvr.QDVRWidget.QDVRWidget` is their control panel.  To get
the frames of a recording as arrays, open it with
:func:`~QVideo.dvr.formats.openVideo`: the reader is indexed and iterated
like a list, with no thread and no clock.

:class:`~QVideo.lib.QFilterPipeline.QFilterPipeline` and
:class:`~QVideo.lib.QVideoScreen.QVideoScreen` are latest-wins.  The pipeline
keeps ``depth`` waiting frames (one by default) and reports its drops with
``framesDropped``; the screen shows at most one frame per throttle
interval.

The screen also guards the GUI thread.  A queued connection would leave
every frame in the GUI thread's event queue while the thread is busy (a
modal dialog, a window drag), and three seconds of a 200 fps, 2048 x 2048
camera would hold 1.5 GB.  The screen therefore receives frames through a
:class:`~QVideo.lib.QFrameRelay.QFrameRelay`, which keeps only the newest
frame and wakes the GUI thread at most once; the same stall then holds
about 13 MB.  The capture thread never waits for it.  Code that needs the
same protection for its own GUI-thread consumer wraps the source in a
relay and connects to ``relay.newFrame``.  The detection overlays (trackpy, YOLO) run one frame at a time
on a worker and skip the frames that arrive meanwhile.  Interactive
overlays, which draw graphics and respond to the user in the GUI thread,
have no worker and no policy to choose.

UI layer
--------

:class:`~QVideo.lib.QCameraTree.QCameraTree` is a
``pyqtgraph.ParameterTree`` widget that reads ``camera.properties`` to
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

:class:`~QVideo.lib.QFilterPipeline.QFilterPipeline` runs
:class:`~QVideo.lib.QVideoFilter.VideoFilter` objects on a worker thread
between a source and its consumers (a screen, a recorder, an overlay), so
every consumer sees the same filtered stream and a slow filter never makes
the interface unresponsive.  A
:class:`~QVideo.lib.QFilterRack.QFilterRack` lets the user add, remove,
reorder, and adjust the filters while the program runs, and owns the
pipeline that applies them.  Its thread-free base class,
:class:`~QVideo.lib.QFilterRackWidget.QFilterRackWidget`, applies the
same filters to recorded frames.

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
  :class:`~QVideo.lib.QFilterRack.QFilterRack` panel, which runs its
  filters on a :class:`~QVideo.lib.QFilterPipeline.QFilterPipeline`.
  :class:`~QVideo.demos.trackpydemo.TrackpyDemo` extends it with a
  :class:`~QVideo.overlays.trackpy.QTrackpyWidget` panel and live particle
  markers.
  :class:`~QVideo.demos.yolodemo.YoloDemo` extends it with a
  :class:`~QVideo.overlays.yolo.QYoloWidget` panel and live YOLO
  detection bounding boxes.
* :class:`~QVideo.demos.roidemo.ROIDemo` extends
  :class:`~QVideo.QCamcorder.QCamcorder` with a draggable ROI overlay.
  :class:`~QVideo.demos.compositedemo.CompositeDemo` extends it with a
  :class:`~QVideo.overlays.trackpy.QTrackpyWidget` panel and a
  ``Composite`` checkbox that switches the DVR between recording raw
  frames and recording the rendered scene (video + overlay markers).

.. _shutting-down:

Shutting down
-------------

Several components run a thread of their own: the camera source, the filter
pipeline, the recorder and the detection overlays.  Each has a ``stop()``
method that ends its thread and waits for it to finish.  It is safe to call
more than once.

* :class:`~QVideo.lib.QCameraTree.QCameraTree`: ``tree.stop()`` stops the
  camera source.
* :class:`~QVideo.lib.QFilterPipeline.QFilterPipeline`: ``pipeline.stop()``.
* :class:`~QVideo.lib.QFilterRack.QFilterRack`: nothing; it stops its own
  pipeline when it is deleted.
* :class:`~QVideo.dvr.QDVRWidget.QDVRWidget`: ``dvr.stop()``.
* :class:`~QVideo.dvr.QRecorder.QRecorder` and
  :class:`~QVideo.dvr.QPlayer.QPlayer`: ``recorder.stop()`` and
  ``player.stop()``.
* :class:`~QVideo.overlays.trackpy.QTrackpyWidget` and
  :class:`~QVideo.overlays.yolo.QYoloWidget`: ``widget.stop()``, which they
  also do when they are deleted.

**Quitting the application needs nothing from you.**  Every component stops
itself when the application emits ``aboutToQuit``.

An application that removes part of its interface while it keeps running,
such as a tool window that is closed and opened again, stops what feeds the
part first and deletes it afterward:

1. Stop the camera tree and any pipeline that supplies the part you are
   removing, so that no frame is delivered to a half-deleted interface.
2. Stop the recorder in it.
3. Delete the widget or window (``deleteLater()``).

Qt closes a window by sending a close event to that window only, not to the
widgets inside it, so closing a window does not stop the components that it
contains; stop them as above.  One more rule keeps a program safe: a worker
thread must never delete a Qt object (including a widget) that lives in
another thread.

A component that starts a thread should follow the same pattern: a public,
repeatable ``stop()``, a connection of ``stop`` to ``aboutToQuit``, and a
connection of the widget's ``destroyed`` signal to the thread's ``quit`` and
``wait``.  The overlay example in :doc:`extending` shows it.

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
