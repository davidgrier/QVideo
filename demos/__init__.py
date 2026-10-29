'''Runnable demo applications built on the QVideo framework.

Each demo composes a :class:`~QVideo.lib.QCameraTree.QCameraTree` with one
or more QVideo widgets into a standalone window.  All demos use
:func:`~QVideo.cameras.chooser.choose_camera` to present a camera-selection
dialog at startup, so no camera-specific code is needed in the demo itself.

Recipes
-------
Each demo adds one idea to the demo before it.  A demo overrides
``_setupUi()``, calls ``super()._setupUi()`` first, and then builds its
widget, connects it and adds it to the panel of controls,
``self._controls``.  Its class docstring starts with a summary and a
``Data flow`` sketch of where the frames go.  Read them in this order:

demo
    Live video beside the controls of the camera that makes it.  The
    starting point for building a custom camera application.

histogramdemo
    A live intensity histogram, whose draggable level handles set the
    display range of the screen.

uniformitydemo
    Mean intensity as a function of x and y, to find non-uniform
    illumination.

circulardemo
    A circular-buffer recorder that always holds the last few seconds and
    writes them to disk on request.  It listens to the camera, not to the
    screen.

filterdemo
    A fixed :class:`~QVideo.lib.QFilterRack.QFilterRack` of filters that
    runs on a worker thread, so that a slow filter leaves the interface
    responsive.

trackpydemo
    Particle positions found by trackpy, drawn over the live video.

yolodemo
    The same recipe with YOLO object detection.

filterrackdemo
    A :class:`~QVideo.QCamcorder.QCamcorder` whose frames pass through an
    editable rack, with three recording modes: raw, filtered and displayed.

compositedemo
    A :class:`~QVideo.QCamcorder.QCamcorder` with a trackpy overlay and a
    checkbox that records the rendered scene, markers included.

combineddemo
    Filters, an overlay and composite recording together, as application
    code: a recipe for combining the ideas above.

roidemo
    A :class:`~QVideo.QCamcorder.QCamcorder` with a draggable region of
    interest; only the pixels inside it are recorded.

Running
-------
Each demo can be launched directly::

    python -m QVideo.demos.demo
    python -m QVideo.demos.filterdemo
    python -m QVideo.demos.filterrackdemo
    python -m QVideo.demos.histogramdemo
    python -m QVideo.demos.uniformitydemo
    python -m QVideo.demos.circulardemo
    python -m QVideo.demos.roidemo
    python -m QVideo.demos.trackpydemo
    python -m QVideo.demos.yolodemo
    python -m QVideo.demos.compositedemo
    python -m QVideo.demos.combineddemo

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
from .filterrackdemo import FilterRackDemo
from .histogramdemo import HistogramDemo
from .uniformitydemo import UniformityDemo
from .circulardemo import CircularDemo
from .roidemo import CropROI, ROIDemo
from .trackpydemo import TrackpyDemo
from .yolodemo import YoloDemo
from .compositedemo import CompositeDemo
from .combineddemo import CombinedDemo

