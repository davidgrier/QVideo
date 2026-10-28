Using QVideo in Jupyter
=======================

Installation
------------

In a notebook, install QVideo with the ``%pip`` magic.  Unlike ``pip`` in a
terminal, it installs into the environment that the notebook's kernel uses,
so ``import QVideo`` works afterwards:

.. code-block:: python

   %pip install "QVideo[pyqt6,jupyter]"

The extras do two things.  ``pyqt6`` installs the Qt layer that QVideo
needs (without one, ``import QVideo`` stops with a message that names the
choices), and ``jupyter`` installs :mod:`ipywidgets`, which the camera
chooser, the property panel and the live view use.  OpenCV and the other
required packages come with QVideo.

Restart the kernel after the installation (**Kernel > Restart**), and
reload the browser tab if you installed :mod:`ipywidgets` for the first
time, so that the notebook can draw its widgets.

.. note::

   If ``import QVideo`` still fails, the notebook kernel probably runs in
   another environment than the one you installed into.  Check it:

   .. code-block:: python

      import sys
      print(sys.executable)   # the interpreter where QVideo is installed

   Install into the environment shown, or register a kernel from the right
   environment and select it in the kernel menu:

   .. code-block:: bash

      pip install ipykernel
      python -m ipykernel install --user --name qvideo --display-name "QVideo"

Acquiring a frame
-----------------

.. code-block:: python

   from QVideo import Camera

   camera = await Camera()
   frame  = camera.read()

``await Camera()`` probes all installed backends and opens a camera that
works:

- With one real camera, it opens that camera.  The simulated Noise camera
  is only a fallback, and ``Camera('Noise')`` selects it.
- With no camera, it says that no hardware was found and uses Noise.
- With several real cameras, a chooser appears: select a camera from the
  drop-down and click **Open**.  The cell shows ``[*]`` until you do.

When :mod:`ipywidgets` is not installed the chooser falls back to a
printed summary::

   Available cameras: Flir, OpenCV
   Using Flir. To select a different one: Camera('OpenCV')

If the chooser prints ``HBox(...)`` instead of a drop-down, see
:ref:`jupyter-widgets`.

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

Filtering frames
----------------

``camera.filters`` is a list of filters that ``camera.read()`` and
``camera.live_view()`` apply to every frame, in order.  Use any of the
filters in :mod:`QVideo.filters`, or any function that takes a frame and
returns a frame:

.. code-block:: python

   from QVideo.filters import DarkFrameFilter, GammaFilter

   camera = await Camera()
   gamma = GammaFilter()
   camera.filters = [DarkFrameFilter(), gamma]
   camera.live_view()           # shows the filtered video
   frame = camera.read()        # a filtered frame

Change the list while the feed runs and the next frame uses it:

.. code-block:: python

   camera.filters.append(lambda frame: 255 - frame)
   camera.filters = []          # back to raw frames

Filters have settings, which you change on the filter itself, for example
``gamma.gamma = 0.5``; the documentation of each filter names them.

- A filter that raises is reported with a warning and removed from the
  list; the feed continues with the others.
- A filter that needs several frames before it has a result, such as an
  average, makes ``read()`` take more frames until it has one.
- Filters run in the notebook's own process, one frame at a time, so a slow
  filter lowers the rate of the display but not what the camera captures.

Finding filters by name
~~~~~~~~~~~~~~~~~~~~~~~

``Filter()`` lists the filters that QVideo provides, and ``Filter('name')``
builds them, so that a notebook needs no imports:

.. code-block:: python

   from QVideo import Camera, Filter

   Filter()                         # ['Blob', 'Canny', 'Cartoon', ...]

   camera = await Camera()
   camera.filters = Filter('Smoothing', 'Canny')
   camera.filters = Filter(['Smoothing', 'Canny'])    # the same

Case and spaces do not matter (``'darkframe'`` finds ``'Dark Frame'``), and
a name that does not exist raises an error that suggests the nearest ones.
The filters come with their default settings; change them through the list:

.. code-block:: python

   camera.filters[1].threshold1 = 50

A filter that needs a calibration, such as ``'Dark Frame'`` or
``'Flat Field'``, passes frames through until it has one.  Keep the filter
and call ``capture()`` to take the calibration from the next frame:

.. code-block:: python

   camera.filters = Filter('Dark Frame')
   camera.filters[0].capture()

Acquiring a sequence of frames
-------------------------------

.. code-block:: python

   import numpy as np

   frames = [camera.read() for _ in range(50)]
   stack  = np.stack(frames)   # shape: (50, height, width, ...)

.. _jupyter-widgets:

Widgets show up as text
-----------------------

If a cell prints something like ``HBox(children=(Dropdown(...)))``
instead of a drop-down, the notebook received the widget but cannot draw
it.  The Python side is fine; the browser side of :mod:`ipywidgets` is not
loaded.  Try these in order:

1. Run ``import ipywidgets; ipywidgets.IntSlider()`` in a cell.  If a
   slider appears, the problem is in QVideo's cell, not in Jupyter.
2. Reload the browser tab, then rerun the cell.
3. Restart the kernel.  If you installed :mod:`ipywidgets` after JupyterLab
   started, restart JupyterLab as well.
4. Install the browser side into the environment that runs JupyterLab:
   ``pip install -U ipywidgets jupyterlab_widgets``, then restart.
5. Compare ``sys.executable`` in a notebook cell with ``which jupyter`` in
   a terminal.  If they name different environments, install into the one
   that the kernel uses (with ``%pip``).

Meanwhile you do not need widgets: ``Camera('OpenCV')`` opens a camera by
name, and ``camera.read()`` returns a frame.

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
