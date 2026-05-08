Filters
=======

All filters subclass :class:`~QVideo.lib.QVideoFilter.VideoFilter` and are
callable: ``filtered = f(frame)``.  The ``Q``-prefixed variants add a
:class:`~pyqtgraph.parametertree` control panel so they can be inserted into a
:class:`~QVideo.lib.QFilterBank.QFilterBank`.

Median background subtraction
------------------------------

The remedian algorithm [R90]_ computes a pixel-wise median over a sliding
window of ``3 ** order`` frames using only two frame buffers per recursion
level.  :class:`~QVideo.filters.Median.Median` produces a new estimate every
third frame; :class:`~QVideo.filters.MoMedian.MoMedian` produces one on every
frame by rolling the buffer.

.. [R90] P.J. Rousseeuw and G.W. Bassett Jr., "The remedian: a robust
   averaging method for large data sets", *Journal of the American Statistical
   Association*, 85(409):97–104, 1990.

.. automodule:: QVideo.filters.Median
   :members:

.. automodule:: QVideo.filters.MoMedian
   :members:

Normalisation
-------------

These filters divide each incoming frame by a median background estimate,
removing fixed-pattern noise and illumination gradients to reveal foreground
features.  :class:`~QVideo.filters.Normalize.Normalize` uses the batch
:class:`~QVideo.filters.Median.Median` estimator;
:class:`~QVideo.filters.Normalize.SmoothNormalize` uses the rolling
:class:`~QVideo.filters.MoMedian.MoMedian` estimator for lower latency.

.. automodule:: QVideo.filters.Normalize
   :members:

Sample-and-hold background
--------------------------

:class:`~QVideo.filters.QSampleHold.SampleHold` extends
:class:`~QVideo.filters.Normalize.Normalize` with a *hold* mechanism: it
accumulates frames until the background estimate converges, then freezes it
and switches to normalising foreground frames against the held estimate.
Clicking *Reset* in the companion widget triggers a fresh accumulation pass,
which is useful after scene changes.

.. automodule:: QVideo.filters.QSampleHold
   :members:

Blur
----

:class:`~QVideo.filters.QBlurFilter.BlurFilter` applies OpenCV's
``GaussianBlur`` with an adjustable odd-pixel kernel.  It is commonly used
as a pre-processing step to reduce high-frequency sensor noise before
edge detection or thresholding.

.. automodule:: QVideo.filters.QBlurFilter
   :members:

Edge detection
--------------

:class:`~QVideo.filters.QEdgeFilter.EdgeFilter` converts color input to
grayscale and runs OpenCV's Canny edge detector.  The two hysteresis
thresholds (*low* and *high*) are exposed as spinboxes in the companion
widget.  A 2:1 or 3:1 high-to-low ratio is recommended for typical
scientific images.

.. automodule:: QVideo.filters.QEdgeFilter
   :members:

RGB channel selection
---------------------

:class:`~QVideo.filters.QRGBFilter.RGBFilter` extracts a single color channel
(Red, Green, or Blue) from an RGB frame, discarding the other two.  Grayscale
input passes through unchanged.  The companion widget exposes the channel
choice as three radio buttons.

.. automodule:: QVideo.filters.QRGBFilter
   :members:

Threshold
---------

:class:`~QVideo.filters.QThresholdFilter.ThresholdFilter` applies a binary
intensity threshold, producing a black-and-white mask.  Pixels above the
threshold are set to 255; all others are set to 0.  The companion widget
provides a spinbox for the threshold level.

.. automodule:: QVideo.filters.QThresholdFilter
   :members:

Region of interest
------------------

:class:`~QVideo.filters.QROIFilter.ROIFilter` crops each frame to a
rectangular sub-region defined by a top-left corner ``(x, y)`` and
dimensions ``(w, h)``.  When the frame shape is first seen — or whenever
it changes — the ROI parameters are clamped to fit within the frame.
That check costs a single tuple comparison per frame; the clamp itself
runs only on shape changes.  The companion widget provides four spinboxes
for ``x``, ``y``, ``w``, and ``h``, with ``w`` and ``h`` stepping in
multiples of 8 for codec compatibility.

.. automodule:: QVideo.filters.QROIFilter
   :members:

Blob coloring
-------------

:class:`~QVideo.filters.QBlobFilter.BlobFilter` runs OpenCV's connected-
component labeling on a binary (thresholded) frame and assigns each blob a
distinct pseudo-color, making it easy to count and track individual objects
visually.

.. automodule:: QVideo.filters.QBlobFilter
   :members:

YOLO confidence threshold
-------------------------

:class:`~QVideo.filters.QYOLOFilter.QYOLOFilter` post-processes detections
from a YOLO model by suppressing any bounding box whose confidence score
falls below an adjustable threshold.  It is intended to be chained after the
:class:`~QVideo.overlays.yolo.QYoloWidget` analysis step in a filter pipeline.

.. automodule:: QVideo.filters.QYOLOFilter
   :members:
