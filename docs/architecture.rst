Architecture
============

QVideo is organised into four layers.  Each layer depends only on the
layers below it, so individual components can be used in isolation.

.. code-block:: text

   ┌──────────────────────────────────────────────────┐
   │  QCamcorder  Demo  FilterDemo  ROIDemo           │  application layer
   ├──────────────┬───────────────────────────────────┤
   │  QCameraTree │  QVideoScreen  QFilterBank  DVR   │  UI layer
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
under ``self.mutex``.  Attribute access (``camera.fps``) delegates to
registered getters via ``__getattr__``, so subclasses need no explicit
Python properties for camera parameters.

Threading layer — ``QVideo.lib.QVideoSource``
----------------------------------------------

:class:`~QVideo.lib.QVideoSource.QVideoSource` wraps a camera in a
``QThread``, calling ``camera.saferead()`` in a loop and emitting
``newFrame(ndarray)``.  It is the standard way to drive a camera from
the GUI thread.

UI layer
--------

:class:`~QVideo.lib.QCameraTree.QCameraTree` is a
``pyqtgraph.ParameterTree`` widget that reads ``camera._properties`` to
auto-build a control panel — no manual UI code is needed per camera.

:class:`~QVideo.lib.QVideoScreen.QVideoScreen` displays live frames from
a :class:`~QVideo.lib.QVideoSource.QVideoSource`.  It maintains the
video aspect ratio by resizing its containing window whenever the frame
dimensions change.

:class:`~QVideo.lib.QFilterBank.QFilterBank` and
:class:`~QVideo.lib.VideoFilter.VideoFilter` provide a composable
image-processing pipeline that sits between a source and a display widget.

Application layer
-----------------

:class:`~QVideo.QCamcorder.QCamcorder` composes a
:class:`~QVideo.lib.QVideoScreen.QVideoScreen`,
:class:`~QVideo.lib.QCameraTree.QCameraTree`, and
:class:`~QVideo.dvr.QDVRWidget.QDVRWidget` into a single reusable widget.

The :mod:`~QVideo.demos` package provides three ready-to-run applications
built on the framework, following two inheritance chains:

* :class:`~QVideo.demos.demo.Demo` — minimal layout: screen + camera tree.
  :class:`~QVideo.demos.filterdemo.FilterDemo` extends it with a
  :class:`~QVideo.lib.QFilterBank.QFilterBank` panel.
* :class:`~QVideo.demos.ROIdemo.ROIDemo` extends
  :class:`~QVideo.QCamcorder.QCamcorder` with a draggable ROI overlay.

Camera backends
---------------

Each backend lives in ``cameras/<Name>/`` and follows the pattern:

* ``Q<Name>Camera`` — subclasses :class:`~QVideo.lib.QCamera.QCamera`.
* ``Q<Name>Source`` — subclasses
  :class:`~QVideo.lib.QVideoSource.QVideoSource`.
* ``Q<Name>Tree`` — subclasses
  :class:`~QVideo.lib.QCameraTree.QCameraTree` when extra UI logic is
  needed.

The OpenCV backend provides two tree widgets:
:class:`~QVideo.cameras.OpenCV.QOpenCVTree.QOpenCVTree` exposes width and
height as independent integer spinboxes (``-c``);
:class:`~QVideo.cameras.OpenCV.QOpenCVResolutionTree.QOpenCVResolutionTree`
replaces them with a ``"W×H"`` drop-down selector populated by probing the
hardware at startup (``-r``), falling back to spinboxes when only one
resolution is available.

Hardware-specific packages are soft dependencies: the import is wrapped in
``try/except (ImportError, ModuleNotFoundError)``.

GenICam cameras (:mod:`~QVideo.cameras.Genicam`,
:mod:`~QVideo.cameras.Flir`, :mod:`~QVideo.cameras.Vimbax`) discover their
GenTL producer ``.cti`` file at runtime via the ``GENICAM_GENTL64_PATH``
environment variable set by the manufacturer's SDK installer.

:mod:`~QVideo.cameras.Noise` is the reference implementation — no hardware
required, used as a model for tests and for verifying the framework.
