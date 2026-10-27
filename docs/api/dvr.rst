DVR
===

QDVRWidget
----------

.. automodule:: QVideo.dvr.QDVRWidget
   :members:

QCircularDVRWidget
------------------

:class:`~QVideo.dvr.QCircularDVRWidget.QCircularDVRWidget` keeps the most
recent seconds of video in memory and writes them to a file when you click
**Save**.  There is no record cycle: the buffer is always filling, so an
event that has just happened can still be saved.  The widget listens to the
camera, not to the screen, so it holds every frame at the camera's full
rate.  :class:`~QVideo.demos.circulardemo.CircularDemo` is the recipe.

.. automodule:: QVideo.dvr.QCircularDVRWidget
   :members:

QCircularBuffer
---------------

:class:`~QVideo.dvr.QCircularBuffer.QCircularBuffer` is the ring buffer
behind it.  It stores each frame with a time stamp and discards the oldest
frame when it is full.  It writes AVI, MKV and MP4 files with OpenCV, and
HDF5 files with the time of each frame.

.. automodule:: QVideo.dvr.QCircularBuffer
   :members:

QOpenCVWriter
-------------

.. automodule:: QVideo.dvr.QOpenCVWriter
   :members:

QOpenCVReader
-------------

.. automodule:: QVideo.dvr.QOpenCVReader
   :members:

QPyAVWriter
-----------

.. automodule:: QVideo.dvr.QPyAVWriter
   :members:

QPyAVReader
-----------

.. automodule:: QVideo.dvr.QPyAVReader
   :members:

QHDF5Writer
-----------

.. automodule:: QVideo.dvr.QHDF5Writer
   :members:

QHDF5Reader
-----------

.. automodule:: QVideo.dvr.QHDF5Reader
   :members:
