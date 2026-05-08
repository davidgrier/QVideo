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
