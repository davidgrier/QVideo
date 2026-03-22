'''Runnable demo applications built on the QVideo framework.

Each demo composes a :class:`~QVideo.lib.QCameraTree.QCameraTree` with one
or more QVideo widgets into a standalone window.  All demos use
:func:`~QVideo.lib.chooser.choose_camera` to present a camera-selection
dialog at startup, so no camera-specific code is needed in the demo itself.

Demos
-----
demo
    Minimal layout: live video screen alongside a camera control tree.
    The starting point for building a custom camera application.

filterdemo
    Extends :mod:`demo` with a :class:`~QVideo.lib.QFilterBank.QFilterBank`
    panel so that image-processing filters can be toggled and adjusted
    alongside the live feed.

ROIdemo
    Extends :class:`~QVideo.QCamcorder.QCamcorder` with a draggable
    rectangular ROI overlay.  Only the cropped region is saved when
    the DVR records, making it easy to capture a sub-region of interest.

Running
-------
Each demo can be launched directly::

    python -m QVideo.demos.demo
    python -m QVideo.demos.filterdemo
    python -m QVideo.demos.ROIdemo

Camera selection
----------------
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

``cameraID`` is an optional integer index (default ``0``) used when
multiple cameras of the same type are connected.  The flags are mutually
exclusive — only one backend can be selected at a time.

Example::

    python -m QVideo.demos.demo -f        # first FLIR camera
    python -m QVideo.demos.filterdemo -c 1  # second OpenCV camera
'''

from .demo import Demo
from .filterdemo import FilterDemo
from .ROIdemo import ROIFilter, ROIDemo

