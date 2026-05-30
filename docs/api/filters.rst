Filters
=======

All filters subclass :class:`~QVideo.lib.QVideoFilter.VideoFilter` and are
callable: ``filtered = f(frame)``.  The ``Q``-prefixed variants add a
:class:`~pyqtgraph.parametertree` control panel so they can be inserted into a
:class:`~QVideo.lib.QFilterBank.QFilterBank`.

Stateless filters also implement
:meth:`~QVideo.lib.QVideoFilter.VideoFilter.to_code` and participate in
:meth:`~QVideo.lib.QFilterRack.QFilterRack.exportPipeline`, which generates
a standalone ``filter.py`` from the rack's current settings.  Stateful
filters that accumulate information across frames cannot be expressed as a
single-frame function and are omitted from the export with a comment.

Calibration
-----------

These filters correct systematic sensor non-uniformities so that
pixel values reflect the true signal rather than hardware artefacts.
Apply them early in the pipeline — typically as the first two filters
— before any feature-detection or enhancement steps.

:class:`~QVideo.filters.darkframe.DarkFrameFilter` subtracts a stored
dark frame from every incoming image, removing thermal electrons,
amplifier offset, and fixed-pattern noise.  Click *Capture* with the
shutter closed (or lens capped) to average :attr:`nFrames` frames into
the dark reference.  Click *Reset* to clear it and pass frames through
unchanged.

:class:`~QVideo.filters.flatfield.FlatFieldFilter` divides each frame
by a stored flat field reference, correcting pixel-to-pixel quantum
efficiency variation and lens vignetting.  Click *Capture* under
uniform illumination to record the reference; the mean is normalized
to 1.0 so overall brightness is preserved.  For best results, place
this filter after :class:`~QVideo.filters.darkframe.DarkFrameFilter`:
the flat field is then captured from already-dark-subtracted frames
and the correction is automatically dark-corrected.

.. automodule:: QVideo.filters.darkframe
   :members:

.. automodule:: QVideo.filters.flatfield
   :members:

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

Running mean (EMA)
------------------

:class:`~QVideo.filters.momean.MoMean` maintains a per-pixel exponential
moving average (EMA) of the incoming frames:

.. math::

   \hat{B}_t = \alpha\,I_t + (1 - \alpha)\,\hat{B}_{t-1}

where *α* controls how quickly the estimate tracks changes.  A small *α*
produces a heavily smoothed, slow-responding background; *α* = 1 reduces
to a passthrough.  The effective time constant in frames is approximately
1 / *α*.  Unlike the remedian estimators, a new estimate is available on
every frame with no warm-up period.

The companion :class:`~QVideo.filters.momean.QMoMean` widget exposes an
*α* spinbox.

.. automodule:: QVideo.filters.momean
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

Gamma correction
----------------

:class:`~QVideo.filters.gamma.GammaFilter` applies the power-law
transform *output* = (*input* / 255)^γ × 255 to every pixel using a
256-entry look-up table built once when :attr:`~QVideo.filters.gamma.GammaFilter.gamma`
changes.  *γ* < 1 lifts shadows; *γ* > 1 deepens them; *γ* = 1 is the identity.
Because the LUT is applied by ``cv2.LUT``, per-frame cost is independent of image
size.  The same table is applied to every channel, preserving colour balance.
Supports pipeline export.

.. automodule:: QVideo.filters.gamma
   :members:

Exposure correction
-------------------

:class:`~QVideo.filters.exposure.ExposureFilter` provides three
tone-mapping methods selectable at runtime.

**Log** compresses dynamic range via a logarithmic curve — *log(1 + p) / log(256)*
— lifting shadow detail without clipping highlights.  No parameters.

**Sigmoid** applies a smooth S-curve centred at *cutoff* with steepness *gain*.
Low *gain* gives a gentle contrast boost; high *gain* approaches hard clipping.

**CLAHE** (Contrast-Limited Adaptive Histogram Equalization) equalises local
contrast within *tile_size* × *tile_size* tiles, capping amplification at
*clip_limit* to suppress noise amplification.  On colour input, CLAHE is applied
to the L channel in LAB colour space so hue and saturation are preserved.
All three methods support pipeline export.

.. automodule:: QVideo.filters.exposure
   :members:

Difference of Gaussians
-----------------------

:class:`~QVideo.filters.dog.DoGFilter` implements the Difference-of-Gaussians
(DoG) bandpass filter.  It subtracts a wide Gaussian blur (*high_sigma*) from a
narrow one (*low_sigma*), suppressing both slowly-varying background and
high-frequency noise.  The result is displayed as the absolute value scaled to
``uint8``, so both positive and negative excursions appear bright.

DoG is a standard preprocessing step for particle tracking and fluorescence
microscopy: it isolates features at the scale set by *low_sigma* while
removing background and pixel noise.  Colour input is converted to grayscale
before filtering.  Supports pipeline export.

.. automodule:: QVideo.filters.dog
   :members:

Unsharp mask
------------

:class:`~QVideo.filters.unsharp.UnsharpFilter` sharpens each frame by
subtracting a Gaussian-blurred copy (*radius*) scaled by *amount* from the
original, implemented as ``cv2.addWeighted`` so the result is clipped to
``[0, 255]`` without overflow.  *amount* = 0 is a no-op; *amount* = 1 gives
a standard unsharp mask; higher values over-sharpen.  Accepts both grayscale
and colour input.  Supports pipeline export.

.. automodule:: QVideo.filters.unsharp
   :members:

Smoothing
---------

:class:`~QVideo.filters.smoothing.SmoothingFilter` applies OpenCV
smoothing with an adjustable odd-pixel kernel.  Three methods are available:

- ``'box'`` (``cv2.blur``) — uniform box average; fastest of the three,
  O(N) cost independent of kernel size.
- ``'gaussian'`` (``cv2.GaussianBlur``) — weighted average with a Gaussian
  kernel; effective against additive Gaussian noise.
- ``'median'`` (``cv2.medianBlur``) — replaces each pixel with the
  neighbourhood median; excels at removing salt-and-pepper noise while
  preserving edges.

The :class:`~QVideo.filters.smoothing.QSmoothingFilter` widget exposes a
method selector combobox and a width spinbox.  Supports pipeline export.

.. automodule:: QVideo.filters.smoothing
   :members:

Dejitter (video stabilization)
------------------------------

:class:`~QVideo.filters.dejitter.DejitterFilter` corrects translational
camera jitter frame-by-frame using FFT-based phase correlation
(``cv2.phaseCorrelate`` with a Hanning window) to estimate the sub-pixel
shift between each frame and a reference image, then applies the inverse
translation via ``cv2.warpAffine``.

Two reference-update modes are supported:

- **Static** — the reference is fixed to the first frame seen after
  construction or reset.  Subsequent frames are aligned to that origin.
  Best for suppressing mechanical vibration around a fixed position.
- **Rolling** — the reference is updated each frame by an exponential
  moving average (weight *α* on the new frame), so it tracks slow drift
  while only fast jitter is corrected.  Best for long acquisitions where
  deliberate stage motion should be preserved.

Computation runs in a background thread via
:class:`~QVideo.lib.AsyncVideoFilter.AsyncVideoFilter`.
The companion :class:`~QVideo.filters.dejitter.QDejitterFilter` widget
exposes a mode selector, an *α* spinbox (shown only in Rolling mode), and
a *Reset* button to reseed the reference.

.. automodule:: QVideo.filters.dejitter
   :members:

Edge detection
--------------

Three edge-detection filters are available, each suited to different imaging
conditions.  All accept color or grayscale input and return a uint8 edge map.

**Canny** — :class:`~QVideo.filters.edge.EdgeFilter` applies OpenCV's
multi-stage Canny detector [C86]_.  Two hysteresis thresholds (*low* and
*high*) control which gradient-magnitude edges are retained; a 2:1 or 3:1
high-to-low ratio is recommended for typical scientific images.  Canny
produces a clean binary edge map and is the best general-purpose choice.
Supports pipeline export.

**Sobel** — :class:`~QVideo.filters.sobel.SobelFilter` computes a
first-order directional derivative using the Sobel operator.  Three modes
are available: *Horizontal* (∂/∂x), *Vertical* (∂/∂y), and *Magnitude*
(Euclidean magnitude √(Gx² + Gy²), clipped to ``[0, 255]``).  The kernel
size *k* is odd and in {1, 3, 5, 7}.  Sobel is well suited to extracting
directional gradient information or computing gradient-magnitude images for
further analysis.  Supports pipeline export.

**Laplacian** — :class:`~QVideo.filters.laplacian.LaplacianFilter` applies
the discrete Laplacian operator (∇²), returning the absolute value as a
uint8 image.  An optional Gaussian pre-blur with standard deviation *σ*
reduces noise sensitivity; setting *σ* > 0 implements the
Laplacian-of-Gaussian (LoG) operator commonly used to detect blob-like
features at a scale set by *σ*.  Supports pipeline export.

.. [C86] J. Canny, 'A computational approach to edge detection,'
   *IEEE Transactions on Pattern Analysis and Machine Intelligence*
   **8**, 679–698 (1986).

.. automodule:: QVideo.filters.edge
   :members:

.. automodule:: QVideo.filters.sobel
   :members:

.. automodule:: QVideo.filters.laplacian
   :members:

RGB channel selection
---------------------

:class:`~QVideo.filters.rgb.RGBFilter` extracts a single color channel
(Red, Green, or Blue) from an RGB frame, discarding the other two.  Grayscale
input passes through unchanged.  The companion widget exposes the channel
choice as three radio buttons.  Supports pipeline export.

.. automodule:: QVideo.filters.rgb
   :members:

Threshold
---------

:class:`~QVideo.filters.threshold.ThresholdFilter` converts each frame to
grayscale and applies a binary threshold, producing a black-and-white mask.
Four methods are available:

- **Global** — pixels above a fixed *level* are set to 255; all others to 0.
- **Otsu** — the threshold is chosen automatically to minimise intra-class
  intensity variance [O79]_; the *level* parameter is ignored.
- **Adaptive Mean** — the threshold at each pixel is the mean intensity of a
  *block* × *block* neighbourhood minus a constant *C*.
- **Adaptive Gaussian** — like Adaptive Mean, but using a Gaussian-weighted
  neighbourhood mean.

The companion :class:`~QVideo.filters.threshold.QThresholdFilter` widget
exposes a method selector combobox; parameter spinboxes appear and disappear
depending on the selected method.
Supports pipeline export.

.. [O79] N. Otsu, 'A threshold selection method from gray-level histograms,'
   *IEEE Transactions on Systems, Man, and Cybernetics* **9**, 62–66 (1979).

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
multiples of 8 for codec compatibility.  Supports pipeline export.

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

Artistic effects
----------------

Two non-photorealistic rendering filters provide artistic transformations of
each frame.  Both require color (BGR) input; grayscale frames are
automatically promoted to BGR before processing.

**Pencil Sketch** — :class:`~QVideo.filters.artistic.PencilSketchFilter`
applies ``cv2.pencilSketch``, which combines an edge-aware smoothing pass
with a hand-drawn shading model to simulate a pencil drawing.  Three
parameters control the appearance:

- *σ_s* (spatial sigma, 1–200) — controls how large a neighbourhood is
  smoothed together; larger values give bolder strokes.
- *σ_r* (range sigma, 0–1) — controls how much tonal variation is absorbed
  into a single smooth region; smaller values preserve more texture.
- *shade* (0–0.1) — overall darkness of the pencil strokes.

The output can be the three-channel color sketch (default) or the
single-channel grayscale version, toggled via the *Gray* checkbox.
Supports pipeline export.

**Cartoon** — :class:`~QVideo.filters.artistic.CartoonFilter` applies
``cv2.stylization``, which flattens low-contrast regions while sharpening
edges to produce a watercolor/cartoon look.  *σ_s* and *σ_r* carry the
same meanings as above.  Supports pipeline export.

.. note::
   Both filters use OpenCV's domain-transform algorithm, which has
   O(N) pixel complexity but a relatively high constant.  For large
   frames (≥ 1080p) the per-frame cost may be tens of milliseconds; the
   live-view frame rate will drop accordingly while either filter is active.

.. automodule:: QVideo.filters.artistic
   :members:

