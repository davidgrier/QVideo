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
backends (Basler, IDS, MV, VimbaX) and the PySpin-based Spinnaker
backend have not been systematically tested on any platform.

Windows
-------

Windows has not been tested because no Windows system is available
to the maintainer.  Reports from Windows users are welcome; please open
an issue on GitHub with the platform, backend, and SDK versions used.
