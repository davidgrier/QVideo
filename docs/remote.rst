A camera in a process of its own
================================

Some camera libraries hold Python's interpreter lock while they wait for a
frame, and while they hold it every other thread of the program waits too: the
interface stutters or freezes (see :doc:`compatibility`).
:class:`~QVideo.lib.remote.camera.QRemoteCamera` is the remedy.  It runs the
camera in a second process, which has an interpreter and a lock of its own,
and it looks like any other camera to the rest of the program.

When it is used
---------------

You do not have to ask.  The backends that use Harvesters (Basler, IDS, MV
and VimbaX) open this way, on macOS and Linux, whenever the chooser opens
them: in every application that uses :func:`~QVideo.lib.launch`, in
``Camera()`` and in ``python QCamcorder.py -b``.  There is no flag.  The
other backends do not need it, and open in the program: Viva, OpenCV and
the Raspberry Pi camera do not hold the lock while they wait, and neither
does Flir with ``genicam`` 1.6.1b1 (a beta) or later.

Create the camera class yourself, as in ``QBaslerCamera()``, to keep a camera
in the program.  To run a camera that the chooser opens in the program in a
worker, as for Flir with an older ``genicam``, make
``QRemoteCamera('flir')``.

What it fixes
-------------

The interface stays responsive.  With a Blackfly S, the event loop of QHOT
waited a median of 23.5 ms for a turn when the camera ran in the program, and
4.6 ms when it ran in a process of its own (the table in :doc:`compatibility`;
one camera, one program, three runs).  It also keeps the program alive when
the vendor's library crashes: the worker ends, the camera is lost, and the
program says so and goes on.  (This has been tried by killing the worker and
by pulling the cable of a Blackfly S, not by a crash of a vendor's library.)

What it costs, and what it cannot do
------------------------------------

* **A start.**  The worker is a new interpreter that imports QVideo and the
  vendor's library: 3.7 s for OpenCV on the machine that measured it.  The
  program waits for it, up to 30 s, when it opens the camera.  Nothing else
  here has been measured: not the copy of each frame into and out of shared
  memory, nor the delay of a frame or of a setting.  A setting waits for the
  worker, and the worker answers between frames, so it takes up to one frame
  time.
* **Not every frame.**  The program gets the newest frame.  If it is slower
  than the camera, the frames in between are lost.  A camera in the program
  hands over the frames of its driver's queue, late.  A recording that needs
  every frame of a fast camera should be tried, and measured, before it is
  trusted.
* **Only what the camera registers.**  Properties and methods that the camera
  registers cross the process, and so do the node calls that the tree of a
  GenICam camera makes.  Anything else that the backend's class has stays in
  the worker.  A property must be a ``bool``, an ``int``, a ``float`` or a
  ``str``, and a frame must be ``uint8`` or ``uint16``.
* **Not on Windows.**  There is no file descriptor to give to a child there, so
  these backends open in the program and have the defect.

How to use it
-------------

Name the backend by its key in :data:`~QVideo.cameras.chooser.BACKENDS`.  The
noise camera makes an example that runs without hardware:

.. code-block:: python

   from QVideo.lib.remote import QRemoteCamera

   with QRemoteCamera('noise') as camera:
       ok, frame = camera.saferead()
       print(ok, camera.name, frame.shape, frame.dtype)

which prints ``True QNoiseCamera (480, 640) uint8``.  For a Flir it is
``QRemoteCamera('flir', cameraID=1)``.  A camera class that is not in the
table is named ``'module:Class'``, and ``python='/path/to/python'`` chooses the
interpreter of the worker, which must have QVideo.  The object is a
:class:`~QVideo.lib.QCamera.QCamera`, so a
:class:`~QVideo.lib.QVideoSource.QVideoSource`, a
:class:`~QVideo.lib.QCameraTree.QCameraTree` and a recorder use it as they use
any other.

If the worker does not start
----------------------------

Opening raises :exc:`~QVideo.lib.errors.QCameraError` with a message that
begins ``Cannot open the KEY camera``, and the rest says why:

* The camera's own message, for example that no camera was found or that the
  GenTL producer is missing.  A message that is not a ``QCameraError`` (a
  bug, or a key that the table does not have) prints the traceback of the
  worker on the terminal of the program as well.
* ``it did not answer``: the worker took more than 30 s.  The vendor's library
  may be waiting for a camera or a driver.
* ``the worker died``: the process ended before it said anything, for example
  because the interpreter does not have QVideo or the vendor's library.

To see the error as the vendor's library gives it, create the class in the
program, as in ``QFlirCamera()``: nothing is in between.  The worker logs under
``QVideo.remote.worker`` and writes to the terminal that the program was
started from.

The protocol
------------

How the two processes talk, what is guaranteed about frames and what is not,
and what happens when either of them dies, is written once, in
:mod:`QVideo.lib.remote.protocol`.  Read it before writing a backend that
needs the worker, or changing the proxy.
