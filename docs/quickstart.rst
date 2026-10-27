Quickstart
==========

Installation
------------

QVideo needs a Qt binding.  PyQt6 is recommended; PyQt5 is also supported:

.. code-block:: bash

   pip install QVideo[pyqt6]   # PyQt6 (recommended)
   pip install QVideo[pyqt5]   # PyQt5
   pip install QVideo          # use a binding that is already installed

PySide6 (``QVideo[pyside6]``) is experimental: the whole test suite
passes under it in continuous integration, but the interpreter occasionally
crashes while pyqtgraph builds a plot, so it is not yet recommended.

To record video to HDF5 files, add the ``dvr`` extra.  The recorder then
compresses the frames without loss.  The ``av`` extra adds PyAV, which
compresses AVI and MKV video without loss several times faster than OpenCV
does, and also records 16-bit gray frames:

.. code-block:: bash

   pip install QVideo[pyqt6,dvr,av]

QVideo uses PyAV for ``.avi``, ``.mkv`` and ``.mp4`` files if it is
installed, and OpenCV if not.  On macOS, importing PyAV and OpenCV into the
same program prints a one-time warning that both packages contain
the FFmpeg library; QVideo does not use the part of it that clashes.

Run the full camcorder application
-----------------------------------

The quickest way to see QVideo in action is to launch the built-in
camcorder.  Use the flag for your camera type:

.. code-block:: bash

   python -m QVideo -c          # USB webcam via OpenCV
   python -m QVideo -b          # Basler camera
   python -m QVideo -f          # FLIR camera
   python -m QVideo -i          # IDS camera
   python -m QVideo -m          # MATRIX VISION / generic GenICam
   python -m QVideo -v          # Allied Vision VimbaX
   python -m QVideo -p          # Raspberry Pi camera

The camcorder window shows the live feed, a property tree for adjusting
camera settings, and a DVR panel for recording.

Display a live feed in your own application
-------------------------------------------

The minimal wiring is a source connected to a display widget:

.. code-block:: python

   import pyqtgraph as pg
   from QVideo.cameras.Noise import QNoiseSource
   from QVideo.lib import QVideoScreen

   app = pg.mkQApp()

   source = QNoiseSource()
   screen = QVideoScreen()
   screen.source = source

   screen.show()
   source.start()
   app.exec()

:class:`~QVideo.cameras.Noise.QNoiseSource` generates synthetic noise
frames — no hardware required.  Replace it with any other source to use
real hardware:

.. code-block:: python

   from QVideo.cameras.OpenCV import QOpenCVSource   # USB webcam
   from QVideo.cameras.Genicam import QGenicamSource # GenICam camera
   from QVideo.cameras.Basler import QBaslerSource   # Basler camera

The rest of the code is identical — the source, screen, and filter
pipeline do not depend on the underlying hardware.

Add camera controls
-------------------

:class:`~QVideo.lib.QCameraTree` reads the camera's registered
properties and builds a control panel automatically.  Each backend has
a tree class (here the noise camera's ``QNoiseTree``) that opens its
camera and provides the source to display:

.. code-block:: python

   import pyqtgraph as pg
   from QVideo.cameras.Noise import QNoiseTree
   from QVideo.lib import QVideoScreen
   from qtpy.QtWidgets import QHBoxLayout, QWidget

   app = pg.mkQApp()

   tree = QNoiseTree()
   source = tree.source
   screen = QVideoScreen()
   screen.source = source

   window = QWidget()
   layout = QHBoxLayout(window)
   layout.addWidget(screen)
   layout.addWidget(tree)
   window.show()

   source.start()
   app.exec()

Apply image filters
-------------------

Put a :class:`~QVideo.lib.QFilterPipeline.QFilterPipeline` between the source
and the screen.  It runs the filters, in order, on a worker thread of its
own, so even a slow filter never makes the interface unresponsive:

.. code-block:: python

   from QVideo.lib import QFilterPipeline
   from QVideo.filters import SmoothingFilter, EdgeFilter

   pipeline = QFilterPipeline(source, [SmoothingFilter(), EdgeFilter()])
   screen.source = pipeline

The pipeline looks like a source, so a recorder can use it too
(``dvr.source = pipeline``) and record exactly what the screen shows.  If
the filters cannot keep up with the camera, the pipeline processes the
newest frame and counts the frames it skipped (``framesDropped``).  Pass
``depth=8`` to queue up to eight frames instead.  A filter that raises
an exception is logged and removed from the pipeline; the rest keep
working.

For filters you can add, remove, reorder and switch on or off while the
program runs, use a :class:`~QVideo.lib.QFilterRack.QFilterRack`.  It is a
widget that owns the pipeline:

.. code-block:: python

   from QVideo.lib import QFilterRack

   rack = QFilterRack(source=source)
   screen.source = rack.pipeline
   layout.addWidget(rack)

To apply the same filters to recorded frames, or to design a pipeline
without a camera, use the thread-free
:class:`~QVideo.lib.QFilterRackWidget.QFilterRackWidget`.

If a camera will not open
-------------------------

The camera factory reports why a camera could not be opened in one line,
for example ``Flir: Feature not present``, and falls back to the simulated
camera.  To see where in QVideo or in the camera library it failed, turn on
debug logging, which also prints the traceback::

    python -c "import logging
    logging.basicConfig(level=logging.DEBUG)
    from QVideo.QCamcorder import main
    main()" -f

Replace ``-f`` by the flag of your camera (see :doc:`api/demos`).

Next steps
----------

- :doc:`architecture` — how the camera, threading, UI, and filter layers
  fit together.
- :doc:`api/lib` — full API reference for the core abstractions.
- :doc:`api/cameras` — available camera backends and their options.
- :doc:`api/filters` — available image filters.
- :doc:`api/dvr` — recording and playback.
- :doc:`api/demos` — runnable recipes, from a minimal camera and screen to
  filters, detection overlays and recording, to read and combine.
