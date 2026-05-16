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
level.  :class:`~QVideo.filters.median.Median` produces a new estimate every
third frame; :class:`~QVideo.filters.momedian.MoMedian` produces one on every
frame by rolling the buffer.

.. [R90] P.J. Rousseeuw and G.W. Bassett Jr., "The remedian: a robust
   averaging method for large data sets", *Journal of the American Statistical
   Association*, 85(409):97–104, 1990.

.. automodule:: QVideo.filters.median
   :members:

.. automodule:: QVideo.filters.momedian
   :members:

Normalisation
-------------

These filters divide each incoming frame by a median background estimate,
removing fixed-pattern noise and illumination gradients to reveal foreground
features.  :class:`~QVideo.filters.normalize.Normalize` uses the batch
:class:`~QVideo.filters.median.Median` estimator;
:class:`~QVideo.filters.normalize.SmoothNormalize` uses the rolling
:class:`~QVideo.filters.momedian.MoMedian` estimator for lower latency.

.. automodule:: QVideo.filters.normalize
   :members:

Sample-and-hold background
--------------------------

:class:`~QVideo.filters.samplehold.SampleHold` extends
:class:`~QVideo.filters.normalize.Normalize` with a *hold* mechanism: it
accumulates frames until the background estimate converges, then freezes it
and switches to normalising foreground frames against the held estimate.
Clicking *Reset* in the companion widget triggers a fresh accumulation pass,
which is useful after scene changes.

.. automodule:: QVideo.filters.samplehold
   :members:

Smoothing
---------

:class:`~QVideo.filters.smoothing.SmoothingFilter` applies OpenCV
smoothing with an adjustable odd-pixel kernel.  Two methods are available:
``'gaussian'`` (``cv2.GaussianBlur``) and ``'median'`` (``cv2.medianBlur``).
Gaussian blur is effective against additive Gaussian noise; median blur
excels at removing salt-and-pepper noise while preserving edges.
The :class:`~QVideo.filters.smoothing.QSmoothingFilter` widget
exposes a method selector combobox and a width spinbox.

.. automodule:: QVideo.filters.smoothing
   :members:

Edge detection
--------------

:class:`~QVideo.filters.edge.EdgeFilter` converts color input to
grayscale and runs OpenCV's Canny edge detector.  The two hysteresis
thresholds (*low* and *high*) are exposed as spinboxes in the companion
widget.  A 2:1 or 3:1 high-to-low ratio is recommended for typical
scientific images.

.. automodule:: QVideo.filters.edge
   :members:

RGB channel selection
---------------------

:class:`~QVideo.filters.rgb.RGBFilter` extracts a single color channel
(Red, Green, or Blue) from an RGB frame, discarding the other two.  Grayscale
input passes through unchanged.  The companion widget exposes the channel
choice as three radio buttons.

.. automodule:: QVideo.filters.rgb
   :members:

Threshold
---------

:class:`~QVideo.filters.threshold.ThresholdFilter` applies a binary
intensity threshold, producing a black-and-white mask.  Pixels above the
threshold are set to 255; all others are set to 0.  The companion widget
provides a spinbox for the threshold level.

.. automodule:: QVideo.filters.threshold
   :members:

Region of interest
------------------

:class:`~QVideo.filters.roi.ROIFilter` crops each frame to a
rectangular sub-region defined by a top-left corner ``(x, y)`` and
dimensions ``(w, h)``.  When the frame shape is first seen — or whenever
it changes — the ROI parameters are clamped to fit within the frame.
That check costs a single tuple comparison per frame; the clamp itself
runs only on shape changes.  The companion widget provides four spinboxes
for ``x``, ``y``, ``w``, and ``h``, with ``w`` and ``h`` stepping in
multiples of 8 for codec compatibility.

.. automodule:: QVideo.filters.roi
   :members:

Foreground estimation
---------------------

:class:`~QVideo.filters.foreground.ForegroundEstimator` uses
OpenCV's MOG2 Gaussian-mixture background subtractor to maintain a persistent
background model ``B(x, y, t)`` and returns each frame divided by that
background.  For a multiplicative image model ``I = B × F`` the output
approximates the foreground modulation ``F ≈ I / B``.  Unlike the median-based
:class:`~QVideo.filters.normalize.Normalize` pipeline, MOG2 remains accurate
even when foreground objects occupy a pixel for more than half the time, because
the mixture tracks the most persistent Gaussian component rather than a simple
median.

The output is scaled by a configurable *mean* (default 128) and cast to
``uint8``, so that unmodulated pixels — where the frame equals the background —
map to *mean*.  Pixels where the foreground brightens the image map above *mean*;
darker foreground maps below.

The companion :class:`~QVideo.filters.foreground.QForegroundEstimator`
widget exposes two controls: *history* (number of frames integrated into the
model) and *threshold* (the Mahalanobis-distance threshold used to classify a
pixel as foreground).  Changing either control resets the background model and
triggers a fresh learning phase.

.. automodule:: QVideo.filters.foreground
   :members:

Circle transform
----------------

:class:`~QVideo.filters.circletransform.CircleTransformFilter`
computes the orientation alignment transform (OAT) of Krishnatreya & Grier
[KG14]_, which detects circularly symmetric ring-like features.  At each
pixel the gradient orientation is compared against the orientation expected
for a ring centred at every candidate position; summing this evidence over
all ring radii simultaneously produces a detection map whose peaks locate
ring centres.  Because the transform integrates over all radii, no radius
parameter is required.

The gradient field is estimated by Savitzky-Golay differentiation
[SG64]_, controlled by *window* (filter width in pixels, must be odd and
≥ 3) and *polyorder* (polynomial order, must be ≥ 1 and less than *window*).
A larger *window* reduces noise but broadens detected peaks.  The output is
normalised per-frame to ``[0, 255]`` and returned as ``uint8``; bright peaks
indicate ring centres.

Computation runs in a background thread via
:class:`~QVideo.lib.AsyncVideoFilter.AsyncVideoFilter`, keeping the GUI
responsive even for large frames.  The companion
:class:`~QVideo.filters.circletransform.QCircleTransformFilter`
widget exposes a *window* spinbox.

.. [KG14] B.J. Krishnatreya and D.G. Grier, 'Fast feature identification
   for holographic tracking: the orientation alignment transform,'
   *Optics Express* **22**, 12773–12778 (2014).

.. [SG64] A. Savitzky and M.J.E. Golay, 'Smoothing and differentiation of
   data by simplified least squares procedures,' *Analytical Chemistry*
   **36**, 1627–1639 (1964).

.. automodule:: QVideo.filters.circletransform
   :members:

Blob coloring
-------------

:class:`~QVideo.filters.blob.BlobFilter` runs OpenCV's connected-
component labeling on a binary (thresholded) frame and assigns each blob a
distinct pseudo-color, making it easy to count and track individual objects
visually.

.. automodule:: QVideo.filters.blob
   :members:

