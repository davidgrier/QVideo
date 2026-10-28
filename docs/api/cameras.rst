Camera backends
===============

Basler
------

.. automodule:: QVideo.cameras.Basler
   :members:

IDS Imaging
-----------

.. automodule:: QVideo.cameras.IDS
   :members:

MATRIX VISION mvGenTLProducer (universal)
-----------------------------------------

.. automodule:: QVideo.cameras.MV
   :members:

Noise (reference)
-----------------

.. automodule:: QVideo.cameras.Noise
   :members:

OpenCV
------

.. automodule:: QVideo.cameras.OpenCV
   :members:

OpenCV camera list
~~~~~~~~~~~~~~~~~~

A combo box of the cameras that OpenCV can open.  If the
``cv2-enumerate-cameras`` package is installed (the ``opencv`` extra), the
entries carry the names of the cameras; without it they read "Camera 0" and
so on.

.. automodule:: QVideo.cameras.OpenCV.QListCVCameras
   :members:

OpenCV device utilities
~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: QVideo.cameras.OpenCV._devices
   :members:
   :member-order: bysource

GenICam (base)
--------------

.. automodule:: QVideo.cameras.Genicam
   :members:

FLIR
----

.. automodule:: QVideo.cameras.Flir
   :members:

FLIR camera list
~~~~~~~~~~~~~~~~

.. automodule:: QVideo.cameras.Flir.QListFlirCameras
   :members:

Allied Vision VimbaX
--------------------

.. automodule:: QVideo.cameras.Vimbax
   :members:

Raspberry Pi Camera
-------------------

.. automodule:: QVideo.cameras.Picamera
   :members:

Raspberry Pi AI Camera (IMX500)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: QVideo.cameras.Picamera._imx500
   :members:

GenTL diagnostics
-----------------

When a GenICam camera (Flir, Basler, IDS, MV, VimbaX) cannot be opened,
run the diagnostic.  It works even if ``harvesters`` or ``genicam`` are
not installed::

    python -m QVideo.cameras.gentl Spinnaker_GenTL.cti

It checks the Python packages, ``GENICAM_GENTL64_PATH``, the producer
file, and whether the producer can see any cameras.

.. automodule:: QVideo.cameras.gentl
   :members: gentlPaths, findProducer, check
