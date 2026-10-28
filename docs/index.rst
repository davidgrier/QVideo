QVideo
======

QVideo is a Qt framework — compatible with PyQt6 and PyQt5 (PySide6 is
experimental) — for integrating scientific cameras into research applications.
It separates hardware communication, threading, property introspection, and UI
into distinct, composable layers so that adding a new camera backend or
image-processing filter requires minimal boilerplate.

Run the full camcorder application directly::

    python -m QVideo [-b|-c|-f|-i|-m|-p|-r|-v] [cameraID]

.. toctree::
   :maxdepth: 2
   :caption: Contents

   quickstart
   compatibility
   jupyter
   rpihat
   architecture
   backends
   extending
   api/lib
   api/interactive
   api/cameras
   api/filters
   api/overlays
   api/dvr
   api/demos

Indices
-------

* :ref:`genindex`
* :ref:`modindex`
