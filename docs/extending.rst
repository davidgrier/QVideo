Extending QVideo: Filters and Overlays
=======================================

QVideo is designed to be extended.  Adding a new image-processing filter
or a new analysis overlay requires implementing one or two small classes
and no changes to the framework itself.

.. contents:: On this page
   :local:
   :depth: 2

----

Filters
-------

Architecture
~~~~~~~~~~~~

The filter pipeline is split into two layers so that image-processing
logic stays separate from UI concerns.

:class:`~QVideo.lib.VideoFilter.VideoFilter`
   The pure image-processing layer.  Its interface is a two-stage
   ``add`` / ``get`` cycle:

   - :meth:`~QVideo.lib.VideoFilter.VideoFilter.add` — receives one frame
     and updates internal state.
   - :meth:`~QVideo.lib.VideoFilter.VideoFilter.get` — returns the processed
     result (which may depend on multiple past frames).
   - :meth:`~QVideo.lib.VideoFilter.VideoFilter.__call__` — chains ``add``
     and ``get``, so a filter can be used as a plain callable:
     ``output = my_filter(frame)``.

   The default ``add`` stores the frame; the default ``get`` returns it
   unchanged (passthrough).  Subclasses override ``get`` for stateless
   transforms, or both ``add`` and ``get`` for stateful ones.

:class:`~QVideo.lib.VideoFilter.QVideoFilter`
   The Qt widget layer.  Wraps a :class:`~QVideo.lib.VideoFilter.VideoFilter`
   in a checkable :class:`~pyqtgraph.Qt.QtWidgets.QGroupBox`.  When the box
   is checked the filter is applied; when unchecked frames pass through
   unchanged.

   Subclasses extend the UI by overriding :meth:`_setupUi`: call
   ``super()._setupUi()`` first, then add controls to ``self._layout``
   (a horizontal :class:`~pyqtgraph.Qt.QtWidgets.QHBoxLayout`).

:class:`~QVideo.lib.QFilterPipeline.QFilterPipeline`
   Runs :class:`~QVideo.lib.QVideoFilter.VideoFilter` objects, in order, on
   a worker thread between a source and its consumers.  A screen or a
   recorder uses the pipeline as its source.

:class:`~QVideo.lib.QFilterRackWidget.QFilterRackWidget`
   A user-editable list of :class:`~QVideo.lib.QVideoFilter.QVideoFilter`
   widgets.  It runs no thread; calling it applies the switched-on filters
   in the caller's thread.

:class:`~QVideo.lib.QFilterRack.QFilterRack`
   A rack widget that owns a pipeline.  The pipeline runs the filters that
   are switched on, on a worker thread, and follows the rack as the user
   edits it.


Writing a stateless filter
~~~~~~~~~~~~~~~~~~~~~~~~~~

A stateless filter transforms each frame independently.  Override only
:meth:`~QVideo.lib.QVideoFilter.VideoFilter.process`, which receives a frame
and returns the filtered frame.

The example below inverts a frame:

.. code-block:: python

   import numpy as np
   from QVideo.lib.QVideoFilter import VideoFilter, QVideoFilter
   from QVideo.lib.videotypes import Image


   class InvertFilter(VideoFilter):
       '''Invert all pixel values.'''

       def process(self, data: Image) -> Image:
           return 255 - data


   class QInvertFilter(QVideoFilter):
       '''Widget for :class:`InvertFilter`.'''

       def __init__(self, parent=None) -> None:
           super().__init__(parent, 'Invert', InvertFilter())

The ``__init__`` passes three arguments to
:class:`~QVideo.lib.VideoFilter.QVideoFilter`:

- *parent* — the Qt parent widget (may be ``None``)
- *title* — the string shown in the group box border
- *videoFilter* — an instance of your :class:`~QVideo.lib.VideoFilter.VideoFilter`

That is the complete implementation.  ``QInvertFilter`` is immediately usable
anywhere a ``QVideoFilter`` is accepted.

Adding parameters with controls
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Override :meth:`_setupUi` to add spinboxes, sliders, or any other widget.

.. code-block:: python

   import numpy as np
   from qtpy import QtCore, QtWidgets
   from pyqtgraph import SpinBox
   from QVideo.lib.QVideoFilter import VideoFilter, QVideoFilter
   from QVideo.lib.videotypes import Image


   class BrightnessFilter(VideoFilter):
       '''Multiply every pixel by a gain factor.

       Parameters
       ----------
       gain : float
           Multiplicative gain.  Default: ``1.0``.
       '''

       def __init__(self, gain: float = 1.0) -> None:
           super().__init__()
           self.gain = gain

       def process(self, data: Image) -> Image:
           return np.clip(data * self.gain, 0, 255).astype(data.dtype)


   class QBrightnessFilter(QVideoFilter):
       '''Widget for :class:`BrightnessFilter` with a gain spinbox.'''

       def __init__(self, parent=None) -> None:
           super().__init__(parent, 'Brightness', BrightnessFilter())

       def _setupUi(self) -> None:
           super()._setupUi()                     # creates self._layout
           self._layout.addWidget(QtWidgets.QLabel('gain'))
           self._spinbox = SpinBox(self, value=self.filter.gain, step=0.1)
           self._spinbox.valueChanged.connect(self._setGain)
           self._layout.addWidget(self._spinbox)

       @QtCore.Slot(object)
       def _setGain(self, value: float) -> None:
           self.filter.gain = value

The key points:

- ``super()._setupUi()`` must be called first — it creates ``self._layout``
  and configures the group box.
- ``self.filter`` is the :class:`~QVideo.lib.VideoFilter.VideoFilter` instance
  passed to the constructor.
- Use :class:`pyqtgraph.SpinBox` instead of :class:`~pyqtgraph.Qt.QtWidgets.QDoubleSpinBox`
  for numeric controls — it integrates more naturally with the pyqtgraph UI style.


Writing a stateful filter
~~~~~~~~~~~~~~~~~~~~~~~~~

Stateful filters accumulate information across multiple frames before
producing output.  Override both :meth:`~QVideo.lib.VideoFilter.VideoFilter.add`
and :meth:`~QVideo.lib.VideoFilter.VideoFilter.get`.

The example below computes a frame-by-frame difference:

.. code-block:: python

   import numpy as np
   from QVideo.lib.QVideoFilter import VideoFilter, QVideoFilter
   from QVideo.lib.videotypes import Image


   class DifferenceFilter(VideoFilter):
       '''Absolute difference between the current frame and the previous one.'''

       def __init__(self) -> None:
           super().__init__()
           self._prev: Image | None = None

       def add(self, image: Image) -> None:
           self._prev = self.data   # shift current → previous
           self.data = image        # store new frame

       def get(self) -> Image | None:
           if self.data is None or self._prev is None:
               return self.data     # not enough frames yet — return as-is
           diff = self.data.astype(np.int16) - self._prev.astype(np.int16)
           return np.abs(diff).astype(np.uint8)


   class QDifferenceFilter(QVideoFilter):
       '''Widget for :class:`DifferenceFilter`.'''

       def __init__(self, parent=None) -> None:
           super().__init__(parent, 'Frame Difference', DifferenceFilter())

The ``add`` override shifts the old frame to ``self._prev`` before storing
the new one.  ``get`` uses integer arithmetic to avoid uint8 wrap-around,
then clips back to 8-bit.


.. _extending-reference:

Writing a reference filter
~~~~~~~~~~~~~~~~~~~~~~~~~~

Some corrections need a *reference* that the user captures: a dark frame
to subtract, a flat field to divide by.  They all work the same way: the
user clicks *Capture*, the filter averages a number of frames into the
reference, and every later frame is corrected with it.
:class:`~QVideo.lib.QReferenceFilter.ReferenceFilter` does the capturing,
so a new calibration filter is two short methods, and
:class:`~QVideo.lib.QReferenceFilter.QReferenceFilter` supplies the
widget.

.. code-block:: python

   import numpy as np
   from QVideo.lib import ReferenceFilter, QReferenceFilter


   class BiasFilter(ReferenceFilter):
       '''Subtract the average of a few frames from every frame.'''

       def _makeReference(self, mean):
           return mean          # the average of the captured frames

       def _correct(self, frame, reference):
           corrected = frame.astype(np.float32) - reference
           return np.clip(corrected, 0, 255).astype(np.uint8)


   class QBiasFilter(QReferenceFilter):
       display_name = 'Bias'    # the title, and the name in the picker
       filterClass = BiasFilter

``_makeReference`` receives the average of the captured frames as a
floating-point array and returns the reference, or ``None`` if the average
cannot serve as one (a flat field whose mean is zero, for example).
``_correct`` receives a frame and the reference, which have the same shape;
frames of another shape pass through unchanged, as do all frames until the
first capture completes.  The filter has ``capture()``, ``reset()``,
``nFrames``, ``isCapturing``, ``reference`` and a ``captured`` signal
without any further code.

Add the filter to ``filters/__init__.py``, with its tests, as for any other
filter.

.. _extending-export:

Supporting pipeline export
~~~~~~~~~~~~~~~~~~~~~~~~~~

:meth:`~QVideo.lib.QFilterRackWidget.QFilterRackWidget.exportPipeline`
generates a
standalone Python file from the rack's current settings.  It calls
:meth:`~QVideo.lib.QVideoFilter.VideoFilter.to_code` on each enabled filter
and assembles the results.  The default implementation returns ``None``, which
means the filter is silently omitted.  Implementing ``to_code`` makes a
custom filter participate in export.

``to_code`` returns a :class:`~QVideo.lib.QVideoFilter.FilterCode` instance
with three fields:

``imports``
  A :class:`frozenset` of complete import lines required by the generated
  code, e.g. ``frozenset({'import cv2', 'import numpy as np'})``.

``lines``
  A :class:`list` of source lines (no leading indentation).  The variable
  ``image`` holds the current frame on entry and must hold the result on exit.
  Temporary variables should use a leading underscore to avoid collisions
  with the surrounding function scope.

``comment``
  An optional one-line description included as a ``# comment`` above the
  generated block.

**Stateless filter example** — the ``InvertFilter`` from the previous section:

.. code-block:: python

   from QVideo.lib.QVideoFilter import VideoFilter, FilterCode, QVideoFilter
   from QVideo.lib.videotypes import Image
   import numpy as np


   class InvertFilter(VideoFilter):
       '''Invert all pixel values.'''

       def process(self, data: Image) -> Image:
           return 255 - data

       def to_code(self) -> FilterCode:
           return FilterCode(
               imports=frozenset({'import numpy as np'}),
               lines=['image = 255 - image'],
               comment='invert pixel values',
           )

**Filter with parameters** — embed the current parameter values directly in
the generated source so the exported function is self-contained:

.. code-block:: python

   class BrightnessFilter(VideoFilter):
       '''Multiply every pixel by a gain factor.'''

       def __init__(self, gain: float = 1.0) -> None:
           super().__init__()
           self.gain = gain

       def process(self, data: Image) -> Image:
           return np.clip(data * self.gain, 0, 255).astype(data.dtype)

       def to_code(self) -> FilterCode:
           return FilterCode(
               imports=frozenset({'import numpy as np'}),
               lines=[
                   f'image = np.clip(image * {self.gain}, 0, 255).astype(image.dtype)',
               ],
               comment=f'brightness gain={self.gain}',
           )

**Stateful filter** — a filter that accumulates state across frames cannot be
expressed as a single-frame pure function.  Leave ``to_code`` returning ``None``
(the default) and the rack will note the omission in a comment:

.. code-block:: python

   # NOTE: the following filters are stateful and were omitted:
   #   DifferenceFilter


Using filters in a pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Via a filter pipeline** (the filters run on a worker thread, and the screen
and a recorder share one filtered stream):

.. code-block:: python

   from QVideo.lib import QFilterPipeline
   from QVideo.filters import SmoothingFilter, EdgeFilter

   pipeline = QFilterPipeline(source, [SmoothingFilter(), EdgeFilter()])
   screen.source = pipeline
   dvr.source = pipeline

A pipeline takes :class:`~QVideo.lib.QVideoFilter.VideoFilter` objects, or
a rack widget through ``rack=``.

**By name, with a rack** (when the filter class is not imported directly):

.. code-block:: python

   rack = QFilterRack(source=source)
   rack.addByName('Smoothing')
   screen.source = rack.pipeline

----

.. _extending-overlays:

Overlays
--------

Architecture
~~~~~~~~~~~~

Overlays draw analysis results on top of the live video inside
:class:`~QVideo.lib.QVideoScreen.QVideoScreen`.  Each overlay has three
components:

**Worker** (``QObject``, runs in a ``QThread``)
   Performs the heavy computation off the GUI thread.  Receives frames via
   a signal, processes them, and emits results via another signal.  Keeping
   analysis off the GUI thread ensures the video display never stutters.

**Graphics item** (``pyqtgraph.GraphicsObject`` or ``pyqtgraph.ScatterPlotItem``)
   Draws markers in the :class:`~QVideo.lib.QVideoScreen.QVideoScreen` scene.
   Its coordinate system matches the video frame: x increases right, y
   increases downward, with the origin at the top-left corner of the frame.
   Register it with :meth:`~QVideo.lib.QVideoScreen.QVideoScreen.addOverlay`.

**Widget** (:class:`~QVideo.lib.QOverlayWidget.QOverlayWidget`)
   Wires the worker and graphics item together and exposes user-facing
   controls.  The base class runs the thread, hands the worker one frame at
   a time, and has a :attr:`source` property that connects the video source
   and an :attr:`overlay` property that returns the graphics item for
   registration with a screen.  A subclass names the group box and adds
   its controls.


Writing a simple overlay
~~~~~~~~~~~~~~~~~~~~~~~~

The example below marks the brightest pixel in each frame with a crosshair:

.. code-block:: python

   import numpy as np
   from qtpy import QtCore
   import pyqtgraph as pg
   from QVideo.lib import QOverlayWidget
   from QVideo.lib.videotypes import Image


   class _BrightSpotWorker(QtCore.QObject):

       newData = QtCore.Signal(object)   # emits (x, y) tuple or None

       @QtCore.Slot(np.ndarray)
       def process(self, image: Image) -> None:
           gray = np.mean(image, axis=2) if image.ndim == 3 else image
           row, col = np.unravel_index(np.argmax(gray), gray.shape)
           self.newData.emit((col, row))   # (x, y) in pixel coords


   class _BrightSpotOverlay(pg.ScatterPlotItem):

       def __init__(self) -> None:
           super().__init__(pen=pg.mkPen('r'), brush=pg.mkBrush(None),
                            symbol='+', size=20, pxMode=True)

       @QtCore.Slot(object)
       def setFeatures(self, pos) -> None:
           if pos is None:
               self.setData([], [])
           else:
               self.setData(x=[pos[0]], y=[pos[1]])


   class QBrightSpotWidget(QOverlayWidget):
       '''Overlay that marks the brightest pixel in each frame.'''

       def __init__(self, parent=None) -> None:
           super().__init__('Bright Spot', _BrightSpotOverlay(),
                            _BrightSpotWorker(), parent)

The base class does the rest.  A subclass that has controls overrides
``_setupUi``, calls ``super()._setupUi()`` first, and adds rows to the form
layout ``self._layout``; the built-in
:class:`~QVideo.overlays.trackpy.QTrackpyWidget` is an example.

Key design decisions:

- The worker is a ``QObject`` with a slot ``process(image)`` and a signal
  ``newData``; the graphics item has a method ``setFeatures`` that receives
  every result.  The widget calls them, so you never connect them yourself.
- The widget hands the worker a frame only when the overlay is switched on
  and the worker has finished the last one, so the thread is idle when the
  overlay is off and frames never queue up behind a slow analysis.
- ``stop`` ends the worker thread, and it is safe to call twice.  The
  thread stops when the application quits (``aboutToQuit``), when the
  widget closes and when it is deleted (``destroyed``).  See
  :ref:`shutting-down`.
- The check box shows and hides the graphics item, giving immediate visual
  feedback.

Wiring an overlay into an application
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import pyqtgraph as pg
   from QVideo.cameras.Noise import QNoiseSource
   from QVideo.lib import QVideoScreen
   from qtpy.QtWidgets import QApplication, QHBoxLayout, QWidget

   app = QApplication([])

   source = QNoiseSource()
   screen = QVideoScreen()
   source.newFrame.connect(screen.setImage)

   widget = QBrightSpotWidget()
   screen.addOverlay(widget.overlay)   # register graphics item with screen
   widget.source = source              # connect source to worker

   window = QWidget()
   layout = QHBoxLayout(window)
   layout.addWidget(screen)
   layout.addWidget(widget)            # add control widget to UI
   window.show()

   source.start()
   app.exec()

:meth:`~QVideo.lib.QVideoScreen.QVideoScreen.addOverlay` places the graphics
item in the screen's coordinate space.  The item is shown and hidden via
:meth:`~pyqtgraph.Qt.QtWidgets.QGroupBox.toggled` rather than by registering
or unregistering it, so it appears and disappears without any lag.


Composite recording
~~~~~~~~~~~~~~~~~~~

When ``screen.composite = True``, :attr:`~QVideo.lib.QVideoScreen.QVideoScreen.newFrame`
emits the fully rendered scene — video *and* all overlay markers — as an
``(H, W, 4)`` RGBA array.  Connect that signal to a DVR writer to record
the annotated video:

.. code-block:: python

   from QVideo.dvr import QHDF5Writer

   screen.composite = True
   fps = screen.fps or 24
   writer = QHDF5Writer('annotated.h5', fps=fps)
   screen.newFrame.connect(writer.write)
   # call writer.close() or connect finished signal when done

Set ``screen.composite = False`` to revert to recording raw (unannotated) frames.
