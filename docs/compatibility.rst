Compatibility
=============

This page records the platform and backend combinations that have been
verified on real hardware.  The unit tests mock all hardware, so they
cannot substantiate these claims.

*Tested* means the backend was run against a physical camera and
behaved correctly.  Other combinations are expected to work but have
not been checked.

Tested platforms
----------------

.. list-table::
   :header-rows: 1
   :widths: 25 45 30

   * - Backend
     - Platform
     - Status
   * - :class:`~QVideo.cameras.OpenCV.QOpenCVCamera`
     - macOS 14 through 26
     - Tested
   * -
     - Ubuntu 24.04
     - Tested
   * -
     - Raspberry Pi OS (Raspbian)
     - Tested
   * -
     - Windows
     - Not tested
   * - :class:`~QVideo.cameras.Flir.QFlirCamera`
     - macOS 14 through 26
     - Tested
   * -
     - Ubuntu 24.04
     - Tested
   * -
     - Windows
     - Not tested
   * - :class:`~QVideo.cameras.Picamera.QPicamera`
     - Raspberry Pi OS (Raspberry Pi 5)
     - Tested

On macOS 26.7.1 (Tahoe), the OpenCV backend was tested with OpenCV
5.0.0_11 and the FLIR backend with Spinnaker SDK 4.4.0.246.

Python versions
---------------

QVideo itself is pure Python and is tested on Python 3.11 through 3.14.
Its dependencies (the Qt bindings, scipy, numba and others) publish
wheels for new Python releases on their own schedules, so the newest
Python may lag behind.  Python 3.15 is run in continuous integration as
an allowed-failure job until its dependencies catch up.

Other backends
--------------

The Noise backend needs no hardware and runs wherever QVideo does.
The Picamera backend requires a Raspberry Pi.  The remaining GenICam
backends (Basler, IDS, MV, VimbaX) have not been systematically tested
on any platform.

USB 3 cameras
-------------

A USB 3 camera on a cable or port without the SuperSpeed wires still
enumerates and answers every command, but its stream is slow and may
stall: the first frame never arrives and the window freezes.  A GenICam
camera that reports its link speed (``U3VCurrentSpeed``) logs a warning
when the link is slower than SuperSpeed.  Use a USB 3 cable, plug the
camera into a USB 3 port without a hub, and check the speed of the
link (on macOS, ``system_profiler SPUSBHostDataType`` shows 5 Gb/s for
SuperSpeed and 480 Mb/s for a USB 2 link).

Windows
-------

Windows has not been tested because no Windows system is available
to the maintainer.  Reports from Windows users are welcome; please open
an issue on GitHub with the platform, backend, and SDK versions used.

Known issues
------------

GenICam cameras freeze the other threads of the process
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A program that streams a camera through harvesters, such as the Flir
backend, has an interface that lags, because the ``genicam`` package, the
Python binding that harvesters uses, **does not release the interpreter
lock** while it waits for a frame or reads the camera.  Every other Python
thread of the process, the thread of the interface included, waits while
any thread is in such a call.

*Measured* with a Blackfly S BFS-U3-13Y3M (1280 x 1024, 67 frames a
second, USB 3), macOS, harvesters 1.4.3, genicam 1.6.0, Spinnaker 4.4:

.. list-table::
   :header-rows: 1
   :widths: 56 22 22

   * - A counter in the main thread, with the camera streaming
     - GenICam
     - PySpin
   * - Python counter, as a fraction of its speed with no camera
     - 60 %
     - 100 %
   * - NumPy counter (matrix products, which release the lock)
     - 1 to 3 %
     - not measured
   * - Wake-up latency of an unrelated thread
     - 336 times the idle latency [#f1]_
     - 0.061 ms (idle: 0.063 ms)
   * - Longest gap in the main thread
     - 8 to 56 ms
     - 4.7 ms

In QHOT, with the same code and traps being added every 100 ms, the
event loop of the interface waited a median of 28 ms (99th percentile
112 ms) and 3 holograms a second were made with the Flir camera, against
5 ms, 13 ms and 10 holograms a second with an OpenCV camera.

What the evidence says:

- The fault is in the binding and not in the vendor's producer.  The
  producer honors its timeouts (requests of 1, 10 and 100 ms returned
  after 1.6, 12.7 and 65 ms), and FLIR's own wrapper, PySpin, releases
  the lock.  Neither ``_gentl.so`` nor ``_genapi.so`` of the ``genicam``
  package imports ``PyEval_SaveThread``, ``PyEval_RestoreThread`` or
  ``PyGILState_*``.
- A longer wait is worse.  ``harvesters`` waits in slices of
  ``timeout_period_on_update_event_data_call`` (1 ms by default) in a
  Python loop.  A slice of 100 ms leaves one wait a frame and halves the
  CPU use, but it holds the lock for the whole wait: with the camera at
  15 frames a second the longest gap in the main thread went from 7.8 ms
  to 55.7 ms.  The 1 ms polling is the least bad setting.
- The work that the GUI thread does for the camera is also affected.
  ``QGenicamTree`` polls the camera every 200 ms with ``states()``, which
  takes 17 to 18 ms a call (up to 41 ms), five times a second, with the
  lock held.
- Not the cause, measured: the overlay of the program (hiding it changed
  the stalls not at all), the number of buffers (3 or 32), the work that
  the capture thread does for each frame (0.45 ms of 15 ms), the frame
  rate, and the wait slice.

This is a known defect: `genicam/harvesters #508
<https://github.com/genicam/harvesters/issues/508>`_ (open), reported on
Windows with a Spinnaker producer, with the same comparison with PySpin.
It cannot be fixed in ``harvesters``, because the lock is held in the
compiled binding, which the GenICam committee maintains.

.. [#f1] From the report in issue #508, with a Spinnaker producer on
   Windows (0.031 ms idle, 10.5 ms while another thread waits in
   ``fetch()``); we did not measure it for GenICam.

*Spinnaker and PySpin.*  PySpin avoids the problem, but the Spinnaker 4.4.0
SDK for macOS (arm64) ships it only for CPython 3.8, 3.9, 3.10 (macOS 13 or
later) and 3.12 (macOS 14 or later), none for 3.13 or 3.14, and the wheel
requires ``numpy>=1.21,<2.0``: with NumPy 2 installed the import fails.
QVideo and QHOT need Python 3.11 or later and do not use anything that is
new in NumPy 2, but they are tested only with NumPy 2.

The plan to deal with it is in ``TODO.md``, and the programs that measured
it are in ``devel/genicam_gil/``.
