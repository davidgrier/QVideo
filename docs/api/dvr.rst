DVR
===

Recording and playback are done by two objects without a window,
:class:`~QVideo.dvr.QRecorder.QRecorder` and
:class:`~QVideo.dvr.QPlayer.QPlayer`, which choose the file reader or writer
from the extension of the file name with the tables in
:mod:`~QVideo.dvr.formats`.  :class:`~QVideo.dvr.QDVRWidget.QDVRWidget` is
their control panel.  Scripts and notebooks use the recorder and the player
directly, or open a file with :func:`~QVideo.dvr.formats.openVideo` to get
its frames as arrays.

QDVRWidget
----------

.. automodule:: QVideo.dvr.QDVRWidget
   :members:

QRecorder
---------

.. automodule:: QVideo.dvr.QRecorder
   :members:

QPlayer
-------

.. automodule:: QVideo.dvr.QPlayer
   :members:

formats
-------

.. automodule:: QVideo.dvr.formats
   :members:
   :undoc-members:

QBacklogMonitor
---------------

:class:`~QVideo.dvr.QBacklogMonitor.QBacklogMonitor` measures how far the
writer of a recording has fallen behind the camera, and reports it in the
signals ``backlog`` and ``behind``.  :class:`~QVideo.dvr.QRecorder.QRecorder`
uses one, and forwards the signals; deciding what to do about a recording
that falls behind is for the application, and the recorder stops by
default.

.. automodule:: QVideo.dvr.QBacklogMonitor
   :members:

QCircularDVRWidget
------------------

:class:`~QVideo.dvr.QCircularDVRWidget.QCircularDVRWidget` keeps the most
recent seconds of video in memory and writes them to a file when you click
**Save**.  There is no record cycle: the buffer is always filling, so an
event that has just happened can still be saved.  The widget listens to the
camera, not to the screen, so it holds every frame at the camera's full
rate.  The file is written on a thread of its own, so saving does not hold
up the interface.  :class:`~QVideo.demos.circulardemo.CircularDemo` is the
recipe.

.. automodule:: QVideo.dvr.QCircularDVRWidget
   :members:

QCircularBuffer
---------------

:class:`~QVideo.dvr.QCircularBuffer.QCircularBuffer` is the ring buffer
behind it.  It stores each frame with its capture information and discards
the oldest frame when it is full.  It does not write files: the widget does
that, with the writers of :mod:`~QVideo.dvr.formats`.

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
