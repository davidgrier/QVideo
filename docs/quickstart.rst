Quickstart
==========

Installation
------------

Install QVideo with a Qt binding.  PyQt5 and PyQt6 are both supported:

.. code-block:: bash

   pip install QVideo[pyqt5]   # PyQt5
   pip install QVideo[pyqt6]   # PyQt6

To record video to HDF5 files, add the ``dvr`` extra:

.. code-block:: bash

   pip install QVideo[pyqt5,dvr]

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
   python -m QVideo -r          # Allied Vision VimbaX
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
   source.newFrame.connect(screen.setImage)

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
properties and builds a control panel automatically:

.. code-block:: python

   import pyqtgraph as pg
   from QVideo.cameras.Noise import QNoiseCamera, QNoiseSource
   from QVideo.lib import QCameraTree, QVideoScreen
   from qtpy.QtWidgets import QApplication, QHBoxLayout, QWidget

   app = QApplication([])

   camera = QNoiseCamera()
   source = QNoiseSource(camera=camera)
   screen = QVideoScreen()
   tree   = QCameraTree(camera=camera)

   source.newFrame.connect(screen.setImage)

   window = QWidget()
   layout = QHBoxLayout(window)
   layout.addWidget(screen)
   layout.addWidget(tree)
   window.show()

   source.start()
   app.exec()

Apply image filters
-------------------

Insert a :class:`~QVideo.lib.QFilterBank` between the source and
screen to process frames before display:

.. code-block:: python

   from QVideo.lib import QFilterBank
   from QVideo.filters import QBlurFilter, QEdgeFilter

   bank = QFilterBank()
   bank.addFilter(QBlurFilter())
   bank.addFilter(QEdgeFilter())

   source.newFrame.connect(bank.updateFrame)
   bank.newFrame.connect(screen.setImage)

Filters are applied in order.  Enable or disable individual filters at
runtime via their ``enabled`` property.

Next steps
----------

- :doc:`architecture` — how the camera, threading, UI, and filter layers
  fit together.
- :doc:`api/lib` — full API reference for the core abstractions.
- :doc:`api/cameras` — available camera backends and their options.
- :doc:`api/filters` — available image filters.
- :doc:`api/dvr` — recording and playback.
