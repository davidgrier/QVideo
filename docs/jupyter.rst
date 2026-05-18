Using QVideo in Jupyter
=======================

Installation
------------

Install QVideo with pip in the **same environment** that your Jupyter
kernel uses:

.. code-block:: bash

   pip install QVideo

That single command installs QVideo and all required dependencies,
including PyQt5 and OpenCV.  Once it completes, ``import QVideo`` will
work in any notebook running in that environment.

For the interactive camera chooser and the property control panel, also
install :mod:`ipywidgets`:

.. code-block:: bash

   pip install ipywidgets

.. note::

   The most common problem is installing QVideo in one environment while
   Jupyter runs in another.  If ``import QVideo`` still fails after
   installation, confirm that the notebook kernel points to the right
   environment:

   .. code-block:: python

      import sys
      print(sys.executable)   # should be the interpreter where QVideo is installed

   If it is not, either install QVideo into the environment shown, or
   register a kernel from the correct environment:

   .. code-block:: bash

      pip install ipykernel
      python -m ipykernel install --user --name qvideo --display-name "QVideo"

   Then select the **QVideo** kernel in the Jupyter kernel menu.

Acquiring a frame
-----------------

.. code-block:: python

   from QVideo import Camera

   camera = await Camera()
   frame  = camera.read()

``await Camera()`` probes all installed backends, prints which cameras
were found, and opens the first working one.  When multiple cameras are
detected the output looks like::

   Available cameras: OpenCV, Noise
   Using OpenCV. To select a different one: Camera('Noise')

To open the first available camera without any output:

.. code-block:: python

   camera = Camera()
   frame  = camera.read()

To request a specific backend by name:

.. code-block:: python

   camera = Camera('OpenCV')   # USB webcam
   camera = Camera('Basler')   # Basler pylon camera
   camera = Camera('Noise')    # synthetic noise — no hardware required

Displaying a frame
------------------

.. code-block:: python

   import matplotlib.pyplot as plt

   plt.imshow(frame, cmap='gray')   # grayscale
   plt.axis('off')
   plt.show()

Omit ``cmap='gray'`` for color frames.

Adjusting camera properties
----------------------------

Camera properties are accessible as attributes:

.. code-block:: python

   camera.fps      = 30.0
   camera.width    = 1280
   camera.exposure = 0.01   # seconds — camera-dependent

To list all properties the active camera exposes:

.. code-block:: python

   print(list(camera.settings))

Interactive property panel
--------------------------

``camera.controls()`` returns an :mod:`ipywidgets`-based property panel
that exposes all camera settings as interactive inputs.  Place it as the
last expression in a cell to render it inline:

.. code-block:: python

   camera.controls()

Each registered property appears as an appropriate widget:

- **float** with known bounds → slider
- **float** without bounds → numeric text field
- **int** with known bounds → integer slider
- **int** without bounds → integer text field
- **bool** → checkbox
- **string** with a fixed set of values → dropdown
- **string** free-form → text field

Read-only properties are shown but disabled.  Click **Refresh** to
re-read all values from the camera (useful after a resolution change or
other external adjustment).

.. note::

   :mod:`ipywidgets` must be installed for ``camera.controls()`` to work::

       pip install ipywidgets

Live video feed
---------------

``camera.live_view()`` streams frames into an :mod:`ipywidgets` image widget
using an ``asyncio`` background loop — no matplotlib backend setup required:

.. code-block:: python

   live = camera.live_view()

To stop the feed:

.. code-block:: python

   live.stop()

Pass ``fps`` to control the display update rate (default 30):

.. code-block:: python

   live = camera.live_view(fps=10.0)

.. note::

   :mod:`ipywidgets` must be installed (included in the ``jupyter`` extra)::

       pip install "QVideo[jupyter]"

Acquiring a sequence of frames
-------------------------------

.. code-block:: python

   import numpy as np

   frames = [camera.read() for _ in range(50)]
   stack  = np.stack(frames)   # shape: (50, height, width, ...)

Environment notes
-----------------

**Headless servers**: Qt requires a display.  On a headless server set
the platform plugin to ``offscreen`` *before* importing QVideo:

.. code-block:: python

   import os
   os.environ['QT_QPA_PLATFORM'] = 'offscreen'
   from QVideo import Camera

**Multiple USB cameras**: pass ``cameraID`` to select a specific device
index:

.. code-block:: python

   camera = Camera('OpenCV', cameraID=1)   # second USB camera
