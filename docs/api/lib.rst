Core library
============

QCamera
-------

.. automodule:: QVideo.lib.QCamera
   :members:

QVideoSource
------------

.. automodule:: QVideo.lib.QVideoSource
   :members:

Image operations
----------------

.. automodule:: QVideo.lib.imageops
   :members:

FrameInfo
---------

Every frame emitted by :attr:`QVideo.lib.QVideoSource.QVideoSource.newFrame`
is accompanied by a :class:`~QVideo.lib.videotypes.FrameInfo` stamped in the
capture thread.  Slots that need only the image may accept a single
argument; the extra argument is dropped.

.. automodule:: QVideo.lib.videotypes
   :members:

QCameraTree
-----------

.. automodule:: QVideo.lib.QCameraTree
   :members:

QVideoScreen
------------

.. automodule:: QVideo.lib.QVideoScreen
   :members:

QHistogramWidget
----------------

:class:`~QVideo.lib.QHistogramWidget.QHistogramWidget` shows the live
histogram of the pixel intensities on a screen.  Its draggable handles set
the range of intensities that the screen displays.  It watches the screen
and needs no connection to the camera; see
:class:`~QVideo.demos.histogramdemo.HistogramDemo`.

.. automodule:: QVideo.lib.QHistogramWidget
   :members:

QUniformityWidget
-----------------

:class:`~QVideo.lib.QUniformityWidget.QUniformityWidget` plots the mean
intensity along x and along y for every frame that the screen displays.
Flat traces mean that the illumination is uniform.  See
:class:`~QVideo.demos.uniformitydemo.UniformityDemo`.

.. automodule:: QVideo.lib.QUniformityWidget
   :members:

VideoFilter
-----------

:class:`~QVideo.lib.QVideoFilter.VideoFilter` is the base class for all
image-processing filters.  Its ``add`` / ``get`` interface separates frame
ingestion from result production, supporting both stateless transforms
(override ``process`` only) and stateful accumulators (override both ``add``
and ``get``).

Stateless filters can also implement
:meth:`~QVideo.lib.QVideoFilter.VideoFilter.to_code`, which returns a
:class:`~QVideo.lib.QVideoFilter.FilterCode` fragment describing the OpenCV
and NumPy calls the filter makes.
:meth:`~QVideo.lib.QFilterRackWidget.QFilterRackWidget.exportPipeline` collects these
fragments to produce a standalone ``filter.py`` file.  See
:ref:`extending-export` for how to add export support to a custom filter.

.. automodule:: QVideo.lib.QVideoFilter
   :members:

QFilterPipeline
---------------

:class:`~QVideo.lib.QFilterPipeline.QFilterPipeline` runs filters on a worker
thread between a source and its consumers.  It receives ``newFrame`` from
the source, applies the filters in order, and emits ``newFrame`` with the
result and the unchanged
:class:`~QVideo.lib.videotypes.FrameInfo`, so processed frames keep the
capture time and index of the frames they came from.  It has the same
``newFrame``, ``shapeChanged``, ``fps`` and ``shape`` as a
:class:`~QVideo.lib.QVideoSource.QVideoSource`, so a screen or recorder
can use it as its source.

While the worker is busy it keeps up to ``depth`` waiting frames and drops
the oldest when more arrive.  The default ``depth=1`` always processes the
newest frame; a larger depth gives a bounded queue for recording.  Drops
are counted and reported through ``framesDropped``.

A filter that raises is logged, removed from the pipeline, and reported
through ``filterFailed``.  Given a
:class:`~QVideo.lib.QFilterRackWidget.QFilterRackWidget`, the pipeline
follows the rack's switched-on filters and switches off the widget of a
filter that fails.  :class:`~QVideo.lib.QFilterRack.QFilterRack` builds
this pairing for you.

.. automodule:: QVideo.lib.QFilterPipeline
   :members:

QFilterRackWidget
-----------------

:class:`~QVideo.lib.QFilterRackWidget.QFilterRackWidget` is a dynamic,
user-editable list of filters with controls.  It wraps each filter in a
slot that carries a ⋮ drag handle for reordering and a × button for
removal.  Set
:attr:`~QVideo.lib.QFilterRackWidget.QFilterRackWidget.editable` to
``False`` to hide all editing controls while keeping the pipeline callable.

The widget runs no thread.  Calling it applies the filters in the caller's
thread, so use it for recorded frames and for designing a pipeline.  For
a live source use :class:`~QVideo.lib.QFilterRack.QFilterRack`.

The toolbar provides two buttons:

**Add filter…**
  Opens a tree dialog listing all
  :class:`~QVideo.lib.QVideoFilter.QVideoFilter` subclasses exported by
  :mod:`QVideo.filters`, grouped by their
  :attr:`~QVideo.lib.QVideoFilter.QVideoFilter.display_category` class
  attribute.  Category headers are not selectable; clicking a leaf item and
  pressing **OK** (or double-clicking it) adds the filter to the rack.
  Filters without a ``display_category`` appear under *Other*.

**Export…**
  Saves the current pipeline as a standalone Python source file.  Only
  *enabled* (checked) filters are included.  Each filter's
  :meth:`~QVideo.lib.QVideoFilter.VideoFilter.to_code` method provides the
  code fragment and import set; the rack assembles them into a module with a
  ``filter(image: np.ndarray) -> np.ndarray`` function.  Filters that return
  ``None`` from ``to_code`` — typically stateful accumulators such as
  :class:`~QVideo.filters.foreground.ForegroundEstimator` — are skipped and
  noted in a comment.  The generated file is valid, immediately importable
  Python.

A typical exported file looks like this:

.. code-block:: python

   '''Image-processing pipeline generated by QVideo.'''

   import cv2
   import numpy as np


   def filter(image: np.ndarray) -> np.ndarray:
       # Gaussian smoothing, k=5
       image = cv2.GaussianBlur(image, (5, 5), 0)

       # Otsu threshold
       if image.ndim == 3:
           image = image.mean(axis=2).astype(np.uint8)
       image = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

       return image

.. automodule:: QVideo.lib.QFilterRackWidget
   :members:

QFilterRack
-----------

:class:`~QVideo.lib.QFilterRack.QFilterRack` is a
:class:`~QVideo.lib.QFilterRackWidget.QFilterRackWidget` that owns a
:class:`~QVideo.lib.QFilterPipeline.QFilterPipeline` following its filters.
It is the class to use with a live source: the filters run on a worker
thread, a slow filter cannot stall the interface or the camera, and the
pipeline keeps the newest frame when it falls behind.  Connect consumers to
its ``pipeline`` attribute::

   rack = QFilterRack(source=camera)
   screen.source = rack.pipeline

.. automodule:: QVideo.lib.QFilterRack
   :members:

Camera chooser
--------------

.. automodule:: QVideo.lib.chooser
   :members:

.. autofunction:: QVideo.lib.launch

QFrameRelay
-----------

.. automodule:: QVideo.lib.QFrameRelay
   :members:

QVideoReader
------------

.. automodule:: QVideo.lib.QVideoReader
   :members:

QVideoWriter
------------

.. automodule:: QVideo.lib.QVideoWriter
   :members:

QScrollPanel
------------

:class:`~QVideo.lib.QScrollPanel.QScrollPanel` shows a panel of controls at
its natural size and adds a vertical scroll bar when the window is too short
for it.  :class:`~QVideo.QCamcorder.QCamcorder` puts its controls in one, so
that applications built on it, such as the filter rack and combined demos,
work on a small screen.

.. automodule:: QVideo.lib.QScrollPanel
   :members:

QSnapshot
---------

:class:`~QVideo.lib.QSnapshot.QSnapshot` captures the most recent frame
from any ``newFrame`` signal and saves it to disk on demand.  It has no
visual presence — drop it into any application as a :class:`~qtpy.QtCore.QObject`
and two keyboard shortcuts become available:

- ``Ctrl+Shift+S`` — save a timestamped PNG to the user's home directory
- ``Ctrl+Shift+Alt+S`` — open a file dialog pre-filled with the same name

The source connected to :meth:`~QVideo.lib.QSnapshot.QSnapshot.newFrame`
determines what is captured: raw frames (``QVideoSource.newFrame``),
filtered frames (``QVideoScreen.newFrame``), or the fully rendered scene
with overlays (``QVideoScreen.newFrame`` with ``composite=True``).

.. automodule:: QVideo.lib.QSnapshot
   :members:

QListCameras
------------

.. automodule:: QVideo.lib.QListCameras
   :members:

clickable
---------

:func:`~QVideo.lib.clickable.clickable` adds a ``clicked()`` signal to any
widget, such as the read-only file name of the DVR panel, which opens a file
dialog when it is clicked.

.. automodule:: QVideo.lib.clickable
   :members:

Camera errors
-------------

Camera backends raise these exceptions when a camera cannot be opened.
The messages say what is missing and what to do about it.

.. automodule:: QVideo.lib.errors
   :members:

GenTL diagnostics
-----------------

When a GenICam camera (Flir, Basler, IDS, MV, VimbaX) cannot be opened,
run the diagnostic.  It works even if ``harvesters`` or ``genicam`` are
not installed::

    python -m QVideo.lib.gentl Spinnaker_GenTL.cti

It checks the Python packages, ``GENICAM_GENTL64_PATH``, the producer
file, and whether the producer can see any cameras.

.. automodule:: QVideo.lib.gentl
   :members: gentlPaths, findProducer, check

QCamcorder
----------

.. automodule:: QVideo.QCamcorder
   :members:
