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

Choosing and opening a camera
-----------------------------

The module holds the table of backends, with the flag that selects each
one (``-c``, ``-f`` and so on), the code that opens a camera from the
table, and the chooser that turns the flags of a command line into an open
camera and its controls.
:func:`~QVideo.cameras.chooser.open_first` opens the first camera of a
list of candidates that works, and says why the others did not; the
chooser and ``Camera()`` both use it.

.. automodule:: QVideo.cameras.chooser
   :members:
