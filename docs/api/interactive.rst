Notebook and script interface
=============================

``Camera()`` and ``Filter()`` are the front door for notebooks and
scripts.  The chapter :doc:`../jupyter` describes how to use them.

.. automodule:: QVideo.interactive
   :members:

Camera
------

.. autofunction:: QVideo.interactive.camera.Camera

.. autoclass:: QVideo.interactive.camera._CameraProxy
   :members: read, filters, live_view, stop_live_view, controls

Filter
------

.. autofunction:: QVideo.interactive.filter.Filter
