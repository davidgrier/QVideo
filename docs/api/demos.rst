Demos
=====

Runnable demo applications built on the QVideo framework.

Each demo composes a :class:`~QVideo.lib.QCameraTree.QCameraTree` with one
or more QVideo widgets into a standalone window.  All demos use
:func:`~QVideo.lib.chooser.choose_camera` to present a camera-selection
dialog at startup, so no camera-specific code is needed in the demo itself.

The default application is :class:`~QVideo.QCamcorder.QCamcorder` and can
be launched via the package entry point::

    python -m QVideo [-b|-c|-f|-i|-m|-p|-r|-v] [cameraID]

Each demo can also be launched directly::

    python -m QVideo.demos.demo
    python -m QVideo.demos.filterdemo
    python -m QVideo.demos.ROIdemo
    python -m QVideo.demos.trackpydemo
    python -m QVideo.demos.yolodemo
    python -m QVideo.demos.compositedemo

All demos accept the same command-line flags to select a camera backend.
If no flag is given, a noise camera is used as a fallback.

.. code-block:: text

    -b [cameraID]   Basler camera (requires pylon SDK)
    -c [cameraID]   OpenCV camera
    -f [cameraID]   FLIR camera (requires Spinnaker SDK)
    -i [cameraID]   IDS Imaging camera (requires IDS peak SDK)
    -m [cameraID]   MATRIX VISION mvGenTLProducer (universal GenICam, not FLIR)
    -p [cameraID]   Raspberry Pi camera module (requires picamera2)
    -v [cameraID]   Allied Vision VimbaX camera
    -h              Show help and exit

Demo
----

The base demo displays a live video screen alongside a camera control tree.
It is the common superclass for all other demos and can be used as a minimal
starting point for custom applications.

.. automodule:: QVideo.demos.demo
   :members:

FilterDemo
----------

Extends the base :class:`~QVideo.demos.demo.Demo` with an image-filter bank
below the camera controls.  All filters registered in
:mod:`QVideo.filters` can be toggled and configured while the camera
is streaming.

.. automodule:: QVideo.demos.filterdemo
   :members:

ROIdemo
-------

Extends :class:`~QVideo.QCamcorder.QCamcorder` with a draggable rectangular
region-of-interest (ROI) overlay.  When active, only the pixels inside the
ROI are passed to the DVR, enabling high-rate recording of a cropped region
without capturing the full frame.

.. automodule:: QVideo.demos.ROIdemo
   :members:

TrackpyDemo
-----------

Extends the base :class:`~QVideo.demos.demo.Demo` with a
:class:`~QVideo.overlays.trackpy.QTrackpyWidget` control panel.  Detected
particle positions are rendered as a scatter-plot directly on the live video
screen using the Crocker–Grier algorithm via
`trackpy <https://soft-matter.github.io/trackpy/>`_.

.. automodule:: QVideo.demos.trackpydemo
   :members:

YoloDemo
--------

Extends the base :class:`~QVideo.demos.demo.Demo` with a
:class:`~QVideo.overlays.yolo.QYoloWidget` control panel.  Detected object
bounding boxes are rendered as labeled rectangles on the live video screen
using a YOLO model via the `Ultralytics <https://docs.ultralytics.com/>`_
library.

.. automodule:: QVideo.demos.yolodemo
   :members:

CompositeDemo
-------------

Extends :class:`~QVideo.QCamcorder.QCamcorder` with a trackpy particle-
detection overlay and a *Composite* recording mode.  When the *Composite*
checkbox is enabled, the DVR records the fully rendered scene — video frame
plus particle markers — rather than the raw camera frames.

.. automodule:: QVideo.demos.compositedemo
   :members:
