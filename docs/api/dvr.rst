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

HDF5 files
----------

A recording to HDF5 is one dataset of frames and one array of metadata for
each frame, written in the single-writer, multiple-reader mode of HDF5 and
flushed about once a second.  If the program stops without closing the
file, the frames up to the last flush are in it, and another program can
read the file while it is written.  Any HDF5 tool reads it; with ``h5py``::

   import h5py

   with h5py.File('run.h5', 'r', swmr=True) as f:
       frames = f['frames']            # (N, height, width) or (N, h, w, 3)
       seconds = f['timestamp'][()]    # capture time of each frame [s]
       image = frames[100]

The file also holds ``index``, the number that the source gave each frame,
and ``hardware_timestamp``, the camera's own time for each frame, which is
``nan`` if the camera has none.  The attributes are ``format_version``,
``Timestamp`` (the UNIX time of the first frame) and ``fps``.
:class:`~QVideo.dvr.QHDF5Reader.QHDF5Reader` also reads the files of
version 1, which had a dataset for each frame in a group named ``images``.

QHDF5Writer
-----------

.. automodule:: QVideo.dvr.QHDF5Writer
   :members:

QHDF5Reader
-----------

.. automodule:: QVideo.dvr.QHDF5Reader
   :members:
