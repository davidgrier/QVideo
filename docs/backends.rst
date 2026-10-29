Writing a camera backend
========================

QVideo is for scientific imaging with widely available cameras, and the
list of cameras that it supports grows when people who own them add them.
This chapter takes you from nothing to a backend that the rest of QVideo
(the live view, the controls, the recorder, the filters and the notebook
interface) can use without knowing anything about your hardware.

.. contents:: On this page
   :local:
   :depth: 2

----

What a backend is
-----------------

A backend is a small package in ``cameras/`` with three classes:

``Q<Name>Camera``
   Talks to the hardware.  It subclasses
   :class:`~QVideo.lib.QCamera.QCamera`.  This is the only class that you
   must write by hand.
``Q<Name>Source``
   Runs the camera in a thread of its own.  It is three lines.
``Q<Name>Tree``
   The controls.  It is three lines, because
   :class:`~QVideo.lib.QCameraTree.QCameraTree` builds the controls from
   the properties that the camera registers.

You do not write threads, locks, controls, recording or display.  The
framework provides them, and the rest of this chapter explains the contract
that makes that possible.

:mod:`QVideo.cameras.Noise` is the reference.  It needs no hardware, so
you can read it, run it and copy it:

.. code-block:: bash

   python -m QVideo.cameras.Noise._camera

----

The contract
------------

Three methods
~~~~~~~~~~~~~

A camera implements three methods and nothing else is required.

``_initialize() -> bool``
   Open the device and register its properties.  Return ``True`` on
   success.  If the camera cannot be opened, raise a
   :class:`~QVideo.lib.errors.QCameraError` whose message tells a
   scientist what is wrong and what to do about it (see
   `Failing helpfully`_), rather than returning ``False``.

``_deinitialize()``
   Release the device, so that it can be opened again, by this program or
   by another.

``read() -> (bool, ndarray | None)``
   Return ``(True, frame)`` for a frame and ``(False, None)`` if none
   could be read.  It blocks until a frame is ready, and returns
   ``(False, None)`` if the camera is closed.

``open()`` and ``close()`` come from the base class.  They may be called
repeatedly, and the camera is a context manager (``with camera:``).

Frames
~~~~~~

A frame is a NumPy array of unsigned integers:

- ``(height, width)`` for a gray image, or ``(height, width, 3)`` for a
  color image with the channels in **RGB** order.  (OpenCV delivers BGR;
  convert it, as :mod:`QVideo.cameras.OpenCV` does.)
- ``uint8``, or ``uint16`` for cameras with more than eight bits.
- Every call returns a **new** array.  Never return a view of a buffer that
  the driver reuses; copy it.  A frame can sit in a queue or in a recorder
  long after the next one has been read.

Properties
~~~~~~~~~~

Everything that a user can adjust is a *property*.  Register it with
:meth:`~QVideo.lib.QCamera.QCamera.registerProperty` and it appears in
the controls, in ``camera.settings``, as an attribute (``camera.gain``)
and in the notebook interface, with no further work:

.. code-block:: python

   register = self.registerProperty
   register('gain', getter=self._getGain, setter=self._setGain,
            ptype=float, minimum=0., maximum=24.)
   register('exposure', ptype=float, minimum=1e-4, maximum=1.)
   register('serial', getter=lambda: self._serial, setter=None, ptype=str)
   register('mode', getter=..., setter=..., ptype=str,
            limits=['mono', 'color'])

- ``ptype`` is ``bool``, ``int``, ``float`` or ``str``.  The getter must
  return that type.
- With no getter and setter, the property reads and writes the attribute
  ``self._<name>``.  This is the short form that the Noise camera uses.
- ``setter=None`` makes a property read-only.
- ``minimum``, ``maximum`` and ``step`` shape the control.  ``limits`` (a
  list of values) turns a ``str`` property into a drop-down.
- Properties may be registered at any time, including inside
  ``_initialize``, which is how a backend publishes whatever features the
  hardware reports.

Register ``width`` and ``height`` (``int``) and ``fps`` (``float``).  The
base class derives ``camera.shape`` from the first two, and the display,
the recorder and the notebook interface depend on it.  If your hardware
changes its frame size, emit ``shapeChanged`` after the change.

If your hardware names its features after a standard, as GenICam does
(``Width``, ``Height``, ``AcquisitionFrameRate``), register them under
those names and say which names stand for ``width``, ``height`` and
``fps`` in the dict :attr:`~QVideo.lib.QCamera.QCamera.aliases`::

    self.aliases.update(width='Width', height='Height',
                        fps='AcquisitionFrameRate')

An alias is not a property: it does not appear in ``properties`` or in
``settings``, and the tree shows the standard names.  But ``camera.width``,
``camera.fps = 30``, ``get('width')``, ``set('fps', 30)`` and ``shape``
all find the property that the alias stands for.

``fps`` is the rate that was asked for.  If the camera can report the rate
that it delivers, which can be lower, override ``actualFps``; the recorder
uses it.

Actions that are not values, such as *auto-focus once*, are registered with
:meth:`~QVideo.lib.QCamera.QCamera.registerMethod`.

Threads and locks
~~~~~~~~~~~~~~~~~

Your camera is read by one thread while another changes its settings.
The base class handles this: every registered getter, setter and method,
and every frame read through ``saferead``, runs holding one lock.  So:

- **Do not write locks of your own.**  A setter can safely stop the
  acquisition, change a mode and restart it, because nothing else can
  touch the device in between.
- Never take the lock from code above the camera, and do not call camera
  getters from the GUI thread once per frame.  A backend that must be
  polled by a GUI offers a snapshot method, as
  :meth:`~QVideo.cameras.Genicam.QGenicamCamera.state` does.

Timestamps
~~~~~~~~~~

The source stamps each frame with the time that it arrived.  If your
camera also stamps frames with its own clock, which is more accurate,
store it in ``self.hardwareTimestamp`` (in seconds) inside ``read``.  The
source copies it into the frame's
:class:`~QVideo.lib.videotypes.FrameInfo`.  Leave it ``None`` otherwise.

Failing helpfully
~~~~~~~~~~~~~~~~~

Most support questions about cameras are about drivers.  Make your backend
explain itself:

- Raise :class:`~QVideo.lib.errors.QDriverError` when the software that is
  needed is missing: "Install the Foo SDK from ... and set ...".
- Raise :class:`~QVideo.lib.errors.QDeviceError` when the driver works and
  the camera does not: "No Foo camera was found; check the cable, and that
  no other program has it open".
- Say what to do, in the words a graduate student will understand at 11 pm.

``Camera()`` shows these messages when it cannot open anything, and the
conformance suite does not need them, so they are easy to forget.  Don't.

----

A complete example
------------------

This camera synthesizes a moving gradient.  It is short, but it is a real
backend: it passes the conformance suite, and it works in the camcorder and
in a notebook.  Replace the body of ``read`` and ``_initialize`` with calls
to your SDK to make it yours.

.. code-block:: python

   import time
   import numpy as np
   from QVideo.lib import QCamera


   class QGradientCamera(QCamera):

       '''A camera that makes a moving gradient (no hardware).'''

       def __init__(self, *args, cameraID: int = 0, **kwargs) -> None:
           super().__init__(*args, **kwargs)
           self._width = 640
           self._height = 480
           self._fps = 30.
           self._gain = 1.
           register = self.registerProperty
           register('width', ptype=int)
           register('height', ptype=int)
           register('fps', ptype=float, minimum=1., maximum=100.)
           register('gain', ptype=float, minimum=0., maximum=2.)
           self.open()

       def _initialize(self) -> bool:
           self._frames = 0
           return True

       def _deinitialize(self) -> None:
           pass

       def read(self) -> QCamera.CameraData:
           if not self.isOpen():
               return False, None
           time.sleep(1. / self._fps)
           x = np.linspace(0., 255. * self._gain, self._width)
           image = np.roll(x, self._frames)[None, :].repeat(self._height, 0)
           self._frames += 1
           return True, np.clip(image, 0, 255).astype(np.uint8)

``width``, ``height`` and ``fps`` use the short form of ``registerProperty``
(the attributes ``_width``, ``_height`` and ``_fps``), so there is no getter
or setter to write.  Because ``read`` returns a freshly computed array
every time, the frames are independent.

The source and the tree are the same for every backend:

.. code-block:: python

   from QVideo.lib import QVideoSource, QCameraTree


   class QGradientSource(QVideoSource):

       def __init__(self, *args, camera=None, **kwargs) -> None:
           super().__init__(camera or QGradientCamera(*args, **kwargs))


   class QGradientTree(QCameraTree):

       def __init__(self, *args, camera=None, cameraID: int = 0,
                    **kwargs) -> None:
           super().__init__(QGradientSource(camera=camera), *args, **kwargs)

Try it:

.. code-block:: python

   from qtpy import QtWidgets
   from QVideo.lib import QVideoScreen

   app = QtWidgets.QApplication([])
   tree = QGradientTree().start()
   screen = QVideoScreen()
   screen.source = tree.source
   screen.show()
   tree.show()
   app.exec()

----

Test it with the conformance suite
----------------------------------

``tests/conformance.py`` states what the rest of QVideo expects of any
camera.  It checks, for example, that a camera can be opened and closed
repeatedly, that frames are independent arrays whose shape agrees with
``camera.shape``, that every property reads back as the type it declares
and keeps its value when it is set to it, that settings can change while
frames are being read, and that a source can stream the camera and stop.
It needs no hardware if you give it a simulated device.

Adopting it takes a file ``tests/test_conformance_<name>.py``:

.. code-block:: python

   import unittest
   from QVideo.tests.conformance import CameraConformance
   from mygradient import QGradientCamera


   class TestGradientCameraConforms(CameraConformance, unittest.TestCase):

       def makeCamera(self):
           return QGradientCamera()

Run it with ``python -m pytest tests/test_conformance_gradient.py``.  If a
check fails, fix the camera.  The suite describes what the framework
relies on, and a camera that breaks it will fail somewhere more confusing
later.  If you think a check is wrong for every camera, open an issue.

**A simulated device is the contribution that matters most.**  Few
contributors have the same camera as the person who reviews the pull
request.  A backend whose SDK is replaced by a mock in the tests can be
checked, and kept working, by anyone.  How to build the mock:

- Hardware packages are soft dependencies, imported inside
  ``try/except (ImportError, ModuleNotFoundError)``, so that QVideo
  imports without them.  Every name that comes from the package must be
  inside the ``try`` block.
- In the test, put a mock module into ``sys.modules`` **before** importing
  your backend, then patch the class that opens the device.  Look at
  ``tests/test_conformance_genicam.py``, which fakes a GenICam device, and
  ``tests/test_conformance_opencv.py``, which plays a video file as a
  camera.
- Add ``tests/test_q<name>camera.py`` for what is specific to your camera:
  error messages, unusual properties, behavior when the device disappears.

Tests never use real hardware.

----

Register the backend
--------------------

Four small edits make ``Camera()``, the command-line flags and the
documentation find your backend:

1. ``cameras/chooser.py``: add an entry to ``BACKENDS`` (module, camera class,
   tree class, label, and the flag character and help string that select
   the camera on the command line) and put the key in
   ``_DISCOVERY_ORDER``.  Order matters: ``Camera()`` tries the earlier
   entries first, and the synthetic Noise camera stays last.
2. ``QCamcorder.py``: add the flag to the list in the module docstring.
3. ``demos/__init__.py``: add the flag to the list in its docstring.
4. ``docs/api/cameras.rst``: add an ``automodule`` entry.

Also add the package to the ``packages`` and ``package-dir`` tables in
``pyproject.toml``, and an optional dependency (an *extra*) that installs
the SDK's Python package, if there is one.  Describe how the camera was
tested, and on which platform, in ``docs/compatibility.rst``: say
honestly what was verified on hardware and what only passes against a
mock.

----

Checklist
---------

Before you open a pull request:

- ``read`` returns a new RGB or gray ``uint8``/``uint16`` array each time.
- ``width``, ``height`` and ``fps`` are registered, or are aliases of
  properties that are.
- Failing to open raises ``QDriverError`` or ``QDeviceError`` with advice.
- ``_deinitialize`` really frees the device, and ``open`` works again.
- The conformance suite passes on a simulated device.
- ``ruff check .`` is clean and the lines are at most 79 characters.
- The four registration edits are made and the documentation builds.
- You tried it in ``python -m QVideo`` and, if you can, in a notebook with
  ``await Camera('<name>')``.

Questions are welcome in `GitHub Issues
<https://github.com/davidgrier/QVideo/issues>`_, and a draft pull request
that does not pass yet is a good way to ask them.

Other kinds of camera
---------------------

The contract assumes one stream of two-dimensional frames, one frame per
``read``.  Cameras that deliver something else, such as depth maps with a
color image, polarization channels or event streams, do not fit it yet.  If
you work with one, open an issue before you start: the right answer is
probably a small extension of the contract, which we would like to design
with someone who has the camera.
