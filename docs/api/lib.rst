Core library
============

QCamera
-------

.. automodule:: QVideo.lib.QCamera
   :members:

QVideoSource
------------

.. automodule:: QVideo.lib.QVideoSource
   :members:

QCameraTree
-----------

.. automodule:: QVideo.lib.QCameraTree
   :members:

QVideoScreen
------------

.. automodule:: QVideo.lib.QVideoScreen
   :members:

QFilterBank and VideoFilter
---------------------------

.. automodule:: QVideo.lib.QFilterBank
   :members:

.. automodule:: QVideo.lib.QVideoFilter
   :members:

AsyncVideoFilter
----------------

:class:`~QVideo.lib.AsyncVideoFilter.AsyncVideoFilter` is a base class for
filters that run heavy computation in a background :class:`~qtpy.QtCore.QThread`
so the GUI remains responsive even when inference is slower than the camera
frame rate.  Frames are dropped rather than queued when the worker is busy,
preventing latency build-up.

Subclasses override :meth:`~QVideo.lib.AsyncVideoFilter.AsyncVideoFilter.process`
(called in the background thread) and inherit :meth:`add` / :meth:`get` /
:meth:`__call__` from the base.

.. automodule:: QVideo.lib.AsyncVideoFilter
   :members:

QFilterRack
-----------

:class:`~QVideo.lib.QFilterRack.QFilterRack` is a dynamic, user-editable
alternative to :class:`~QVideo.lib.QFilterBank.QFilterBank`.  It wraps each
filter in a slot that carries a ⋮ drag handle for reordering and a × button
for removal.  An "Add filter…" toolbar button opens a picker dialog listing
all :class:`~QVideo.lib.QVideoFilter.QVideoFilter` subclasses exported by
:mod:`QVideo.filters`.  Set :attr:`~QVideo.lib.QFilterRack.QFilterRack.editable`
to ``False`` to hide all editing controls while keeping the pipeline callable.

.. automodule:: QVideo.lib.QFilterRack
   :members:

Camera chooser
--------------

.. automodule:: QVideo.lib.chooser
   :members:

QVideoReader
------------

.. automodule:: QVideo.lib.QVideoReader
   :members:

QVideoWriter
------------

.. automodule:: QVideo.lib.QVideoWriter
   :members:

QFPSMeter
---------

.. automodule:: QVideo.lib.QFPSMeter
   :members:

QListCameras
------------

.. automodule:: QVideo.lib.QListCameras
   :members:

QCamcorder
----------

.. automodule:: QVideo.QCamcorder
   :members:
