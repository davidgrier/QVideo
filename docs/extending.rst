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

:class:`~QVideo.lib.QFilterBank.QFilterBank`
   An ordered stack of :class:`~QVideo.lib.VideoFilter.QVideoFilter` widgets.
   :meth:`~QVideo.lib.QFilterBank.QFilterBank.register` appends a filter;
   the bank applies them left-to-right when called.  A
   :class:`~QVideo.lib.QVideoScreen.QVideoScreen` owns one internally
   (``screen.filter``); register filters there to have them applied
   automatically on every displayed frame.


Writing a stateless filter
~~~~~~~~~~~~~~~~~~~~~~~~~~

A stateless filter transforms each frame independently.  Override only
:meth:`~QVideo.lib.VideoFilter.VideoFilter.get`.

The example below inverts a frame:

.. code-block:: python

   import numpy as np
   from QVideo.lib.QVideoFilter import VideoFilter, QVideoFilter
   from QVideo.lib.videotypes import Image


   class InvertFilter(VideoFilter):
       '''Invert all pixel values.'''

       def get(self) -> Image | None:
           if self.data is None:
               return None
           return 255 - self.data


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

       def get(self) -> Image | None:
           if self.data is None:
               return None
           return np.clip(self.data * self.gain, 0, 255).astype(self.data.dtype)


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


Using filters in a pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Via the screen's built-in filter bank** (simplest):

.. code-block:: python

   screen = QVideoScreen()
   screen.filter.register(QBrightnessFilter())
   screen.filter.register(QEdgeFilter())
   screen.filter.setVisible(True)   # show the filter panel

Every frame displayed by the screen passes through the bank automatically.
:meth:`~QVideo.lib.QFilterBank.QFilterBank.setVisible` controls whether
the filter widgets appear in the layout.

**Via a standalone filter bank** (useful when the bank itself is a UI component):

.. code-block:: python

   from QVideo.lib import QFilterBank
   from QVideo.filters import QSmoothingFilter, QEdgeFilter

   bank = QFilterBank()
   bank.register(QSmoothingFilter())
   bank.register(QEdgeFilter())

   source.newFrame.connect(bank.updateFrame)
   bank.newFrame.connect(screen.setImage)

**By name** (when the filter class is not imported directly):

.. code-block:: python

   screen.filter.registerByName('QBrightnessFilter')

----

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

**Widget** (``QGroupBox``)
   Wires the worker and graphics item together and exposes user-facing
   controls.  Exposes a :attr:`source` property that, when set, connects
   the video source to the worker.  Exposes an :attr:`overlay` property
   that returns the graphics item for registration with a screen.


Writing a simple overlay
~~~~~~~~~~~~~~~~~~~~~~~~

The example below marks the brightest pixel in each frame with a crosshair:

.. code-block:: python

   import numpy as np
   from qtpy import QtCore, QtWidgets
   import pyqtgraph as pg
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
       def setPosition(self, pos) -> None:
           if pos is None:
               self.setData([], [])
           else:
               self.setData(x=[pos[0]], y=[pos[1]])


   class QBrightSpotWidget(QtWidgets.QGroupBox):
       '''Overlay that marks the brightest pixel in each frame.'''

       _process = QtCore.Signal(np.ndarray)

       def __init__(self, parent=None) -> None:
           super().__init__('Bright Spot', parent)
           self.setCheckable(True)
           self.setChecked(False)
           self._overlay = _BrightSpotOverlay()
           self._worker = _BrightSpotWorker()
           self._thread = QtCore.QThread(self)
           self._worker.moveToThread(self._thread)
           self._process.connect(self._worker.process)
           self._worker.newData.connect(self._overlay.setPosition)
           self.toggled.connect(self._overlay.setVisible)
           self._thread.start()
           self._source = None
           QtCore.QCoreApplication.instance().aboutToQuit.connect(
               self._cleanup)

       def _cleanup(self) -> None:
           self._thread.quit()
           self._thread.wait()

       @property
       def overlay(self) -> pg.ScatterPlotItem:
           '''The graphics item to register with a screen.'''
           return self._overlay

       @property
       def source(self):
           '''The video source supplying frames to this overlay.'''
           return self._source

       @source.setter
       def source(self, source) -> None:
           if self._source is not None:
               self._source.newFrame.disconnect(self._onNewFrame)
           self._source = source
           if source is not None:
               source.newFrame.connect(self._onNewFrame)

       @QtCore.Slot(np.ndarray)
       def _onNewFrame(self, frame: Image) -> None:
           if self.isChecked():
               self._process.emit(frame)

Key design decisions:

- The ``_process`` signal is a private :class:`~pyqtgraph.Qt.QtCore.Signal`
  on the widget rather than connecting ``source.newFrame`` directly to the
  worker.  This lets ``_onNewFrame`` gate dispatch on ``isChecked()``, so
  the worker thread is idle when the overlay is disabled.
- ``_cleanup`` gracefully stops the worker thread when the application exits.
  Connect it to ``QCoreApplication.instance().aboutToQuit``.
- ``toggled.connect(self._overlay.setVisible)`` hides the markers when the
  group box is unchecked, giving immediate visual feedback.


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
