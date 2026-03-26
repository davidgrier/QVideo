Demos
=====

Runnable demo applications built on the QVideo framework.

Each demo composes a :class:`~QVideo.lib.QCameraTree.QCameraTree` with one
or more QVideo widgets into a standalone window.  All demos use
:func:`~QVideo.lib.chooser.choose_camera` to present a camera-selection
dialog at startup, so no camera-specific code is needed in the demo itself.

Each demo can be launched directly::

    python -m QVideo.demos.demo
    python -m QVideo.demos.filterdemo
    python -m QVideo.demos.ROIdemo
    python -m QVideo.demos.trackpydemo
    python -m QVideo.demos.yolodemo

All demos accept the same command-line flags to select a camera backend.
If no flag is given, a noise camera is used as a fallback.

.. code-block:: text

    -b [cameraID]   Basler camera (requires pylon SDK)
    -c [cameraID]   OpenCV camera
    -f [cameraID]   FLIR camera (requires Spinnaker SDK)
    -i [cameraID]   IDS Imaging camera (requires IDS peak SDK)
    -m [cameraID]   MATRIX VISION mvGenTLProducer (universal GenICam, not FLIR)
    -p [cameraID]   Raspberry Pi camera module (requires picamera2)
    -r [cameraID]   OpenCV camera with resolution drop-down selector
    -v [cameraID]   Allied Vision VimbaX camera
    -h              Show help and exit

Demo
----

.. automodule:: QVideo.demos.demo
   :members:

FilterDemo
----------

.. automodule:: QVideo.demos.filterdemo
   :members:

ROIdemo
-------

.. automodule:: QVideo.demos.ROIdemo
   :members:

TrackpyDemo
-----------

.. automodule:: QVideo.demos.trackpydemo
   :members:

YoloDemo
--------

.. automodule:: QVideo.demos.yolodemo
   :members:
