Filters
=======

All filters subclass :class:`~QVideo.lib.QVideoFilter.VideoFilter` and are
callable: ``filtered = f(frame)``.  The ``Q``-prefixed variants add a
:class:`~pyqtgraph.parametertree` control panel so they can be inserted into a
:class:`~QVideo.lib.QFilterBank.QFilterBank`.

Median background subtraction
------------------------------

.. automodule:: QVideo.filters.Median
   :members:

.. automodule:: QVideo.filters.MoMedian
   :members:

Normalisation
-------------

.. automodule:: QVideo.filters.Normalize
   :members:

Sample-and-hold background
--------------------------

.. automodule:: QVideo.filters.QSampleHold
   :members:

Blur
----

.. automodule:: QVideo.filters.QBlurFilter
   :members:

Edge detection
--------------

.. automodule:: QVideo.filters.QEdgeFilter
   :members:

RGB channel selection
---------------------

.. automodule:: QVideo.filters.QRGBFilter
   :members:

Threshold
---------

.. automodule:: QVideo.filters.QThresholdFilter
   :members:

Blob coloring
-------------

.. automodule:: QVideo.filters.QBlobFilter
   :members:

YOLO confidence threshold
-------------------------

.. automodule:: QVideo.filters.QYOLOFilter
   :members:
