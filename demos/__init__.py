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
'''

from .demo import Demo
from .filterdemo import Demo as FilterDemo
from .ROIdemo import ROIFilter, ROIDemo
