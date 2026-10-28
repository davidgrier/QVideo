Demos
=====

Runnable demo applications built on the QVideo framework.

Each demo composes a :class:`~QVideo.lib.QCameraTree.QCameraTree` with one
or more QVideo widgets into a standalone window.  All demos use
:func:`~QVideo.cameras.chooser.choose_camera` to present a camera-selection
dialog at startup, so no camera-specific code is needed in the demo itself.
Each demo's entry point is a single call to
:func:`~QVideo.lib.launch`, which an application of your own can use in the
same way.

The default application is :class:`~QVideo.QCamcorder.QCamcorder` and can
be launched via the package entry point::

    python -m QVideo [-b|-c|-f|-i|-m|-p|-v] [cameraID]

Each demo can also be launched directly::

    python -m QVideo.demos.demo
    python -m QVideo.demos.histogramdemo
    python -m QVideo.demos.uniformitydemo
    python -m QVideo.demos.circulardemo
    python -m QVideo.demos.filterdemo
    python -m QVideo.demos.filterrackdemo
    python -m QVideo.demos.ROIdemo
    python -m QVideo.demos.trackpydemo
    python -m QVideo.demos.yolodemo
    python -m QVideo.demos.compositedemo
    python -m QVideo.demos.combineddemo

All demos accept the same command-line flags to select a camera backend.
If no flag is given, a noise camera is used as a fallback.

.. code-block:: text

    -b [cameraID]   Basler camera (requires pylon SDK)
    -c [cameraID]   OpenCV camera
    -f [cameraID]   FLIR camera (requires Spinnaker SDK)
    -i [cameraID]   IDS Imaging camera (requires IDS peak SDK)
    -m [cameraID]   MATRIX VISION mvGenTLProducer (universal GenICam, not FLIR)
    -p [cameraID]   Raspberry Pi camera module (requires picamera2)
    -v [cameraID]   Allied Vision VimbaX camera
    -h              Show help and exit

The demos are recipes
---------------------

Each demo adds one idea to the demo before it, so that you can read them in
order and then combine the ideas in an application of your own.  They are
all written the same way:

1. A demo is a widget that takes the camera tree as its first argument.
   :class:`~QVideo.demos.demo.Demo` and
   :class:`~QVideo.QCamcorder.QCamcorder` are the two bases: both make the
   screen and a panel of controls, and both connect the camera to the
   screen.
2. A demo overrides ``_setupUi()`` and calls ``super()._setupUi()`` first.
   It then builds its widget, connects it, and adds it to the panel of
   controls, ``self._controls``.  Everything the demo adds is in that one
   method.
3. Wiring that has to follow the base class, such as displaying a filter
   pipeline instead of the camera, is also done in ``_setupUi()``, because
   the base classes connect the camera before it runs.  Signal connections
   go in ``_connectSignals()``.
4. The class docstring starts with a one-line summary and a ``Data flow``
   sketch that shows where the frames go.

For example, this is all of :class:`~QVideo.demos.histogramdemo.HistogramDemo`
except its documentation:

.. literalinclude:: /../demos/histogramdemo.py
   :language: python
   :pyobject: HistogramDemo._setupUi

Combining ideas is application code, not a framework feature, because only
the application knows which stream each extension needs.
:class:`~QVideo.demos.combineddemo.CombinedDemo` shows how.

The ladder
----------

.. list-table::
   :header-rows: 1
   :widths: 22 18 60

   * - Demo
     - Extends
     - The idea it adds
   * - :class:`~QVideo.demos.demo.Demo`
     - ``QWidget``
     - Live video beside the controls of the camera that makes it.
   * - :class:`~QVideo.demos.histogramdemo.HistogramDemo`
     - ``Demo``
     - A widget that watches the screen, and sets its display range.
   * - :class:`~QVideo.demos.uniformitydemo.UniformityDemo`
     - ``Demo``
     - Another widget that watches the screen.
   * - :class:`~QVideo.demos.circulardemo.CircularDemo`
     - ``Demo``
     - A recorder that listens to the camera, not to the screen.
   * - :class:`~QVideo.demos.filterdemo.FilterDemo`
     - ``Demo``
     - Filters on a worker thread: the screen displays a pipeline.
   * - :class:`~QVideo.demos.trackpydemo.TrackpyDemo`
     - ``Demo``
     - A detector on a worker thread, and an overlay the screen draws.
   * - :class:`~QVideo.demos.yolodemo.YoloDemo`
     - ``Demo``
     - The same recipe with another detector.
   * - :class:`~QVideo.QCamcorder.QCamcorder`
     - ``QWidget``
     - The camera, the screen and a recorder.
   * - :class:`~QVideo.demos.filterrackdemo.FilterRackDemo`
     - ``QCamcorder``
     - Choose which stream the recorder saves: raw, filtered or displayed.
   * - :class:`~QVideo.demos.compositedemo.CompositeDemo`
     - ``QCamcorder``
     - Record the rendered scene, markers included.
   * - :class:`~QVideo.demos.combineddemo.CombinedDemo`
     - ``FilterRackDemo``
     - Filters, an overlay and composite recording together.
   * - :class:`~QVideo.demos.ROIdemo.ROIDemo`
     - ``QCamcorder``
     - Record only the region inside a draggable ROI.

Demo
----

The base demo displays a live video screen alongside a camera control tree.
It is the starting point for the demos that follow and for applications of
your own.

.. automodule:: QVideo.demos.demo
   :members:

HistogramDemo
-------------

A live intensity histogram of the frames the screen displays.  The widget takes
the screen, so it needs no connection of its own.

.. literalinclude:: /../demos/histogramdemo.py
   :language: python
   :pyobject: HistogramDemo._setupUi

.. automodule:: QVideo.demos.histogramdemo
   :members:

UniformityDemo
--------------

Mean intensity across the frames the screen displays, as a function of x and of
y, for finding non-uniform illumination.

.. literalinclude:: /../demos/uniformitydemo.py
   :language: python
   :pyobject: UniformityDemo._setupUi

.. automodule:: QVideo.demos.uniformitydemo
   :members:

CircularDemo
------------

A recorder that always holds the last few seconds.  It listens to the camera,
not to the screen, so it keeps every frame.

.. literalinclude:: /../demos/circulardemo.py
   :language: python
   :pyobject: CircularDemo._setupUi

.. automodule:: QVideo.demos.circulardemo
   :members:

FilterDemo
----------

A fixed rack of filters that runs on a worker thread.  The screen displays the
rack's pipeline instead of the camera, so a slow filter leaves the interface
responsive.

.. literalinclude:: /../demos/filterdemo.py
   :language: python
   :pyobject: FilterDemo._setupUi

.. automodule:: QVideo.demos.filterdemo
   :members:

TrackpyDemo
-----------

Detected particle positions drawn on the live video, using the Crocker-Grier
algorithm of `trackpy <https://soft-matter.github.io/trackpy/>`_.  Detection
runs on its own thread.

.. literalinclude:: /../demos/trackpydemo.py
   :language: python
   :pyobject: TrackpyDemo._setupUi

.. automodule:: QVideo.demos.trackpydemo
   :members:

YoloDemo
--------

Detected objects drawn as labeled boxes on the live video, using a YOLO model
from the `Ultralytics <https://docs.ultralytics.com/>`_ library.

.. literalinclude:: /../demos/yolodemo.py
   :language: python
   :pyobject: YoloDemo._setupUi

.. automodule:: QVideo.demos.yolodemo
   :members:

FilterRackDemo
--------------

A camcorder whose frames pass through an editable
:class:`~QVideo.lib.QFilterRack.QFilterRack`, with three recording modes
selectable at runtime: **Raw** (unfiltered, at the camera's full rate),
**Filtered** (the rack's output, at the full rate) and **Display** (the rack's
output at the throttled display rate).

.. literalinclude:: /../demos/filterrackdemo.py
   :language: python
   :pyobject: FilterRackDemo._setupUi

.. automodule:: QVideo.demos.filterrackdemo
   :members:

CompositeDemo
-------------

A trackpy overlay and a *Composite* checkbox.  When it is checked the recorder
saves the rendered scene, video plus particle markers, instead of the raw
camera frames.

.. literalinclude:: /../demos/compositedemo.py
   :language: python
   :pyobject: CompositeDemo._setupUi

.. automodule:: QVideo.demos.compositedemo
   :members:

CombinedDemo
------------

Filters, an overlay and composite recording together.  The overlay locates
particles in the *filtered* video, and a fourth recording mode saves the
rendered scene.  The module docstring shows the data flow.

.. literalinclude:: /../demos/combineddemo.py
   :language: python
   :pyobject: CombinedDemo._setupUi

.. automodule:: QVideo.demos.combineddemo
   :members:

ROIdemo
-------

A draggable rectangular region of interest.  While recording, only the pixels
inside it are saved, which allows high-rate recording of a cropped region.

.. literalinclude:: /../demos/ROIdemo.py
   :language: python
   :pyobject: ROIDemo._setupUi

.. automodule:: QVideo.demos.ROIdemo
   :members:
