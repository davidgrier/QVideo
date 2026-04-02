Overlays
========

Graphical overlays for :class:`~QVideo.lib.QVideoScreen.QVideoScreen`.

Each overlay is a :class:`pyqtgraph.GraphicsObject` subclass that renders
analysis results directly on the live video image.  A companion
:class:`~pyqtgraph.Qt.QtWidgets.QGroupBox` widget owns the background
worker thread, exposes analysis parameters, and forwards results via a
``newData`` signal.

Typical usage::

    widget = QTrackpyWidget(parent)   # or QYoloWidget
    widget.source = camera_source
    screen.addOverlay(widget.overlay)
    widget.newData.connect(my_slot)

Trackpy
-------

:class:`~QVideo.overlays.trackpy.QTrackpyWidget` detects bright particles in
each video frame using the `trackpy <https://soft-matter.github.io/trackpy/>`_
library, which implements the Crocker–Grier algorithm [CG96]_.  Detected
positions are rendered in real time as a scatter-plot overlay by
:class:`~QVideo.overlays.trackpy.QTrackpyOverlay`.  Particle diameter and
minimum separation are adjustable from the widget.

.. [CG96] J.C. Crocker and D.G. Grier, "Methods of digital video microscopy
   for colloidal studies", *Journal of Colloid and Interface Science*,
   179(1):298–310, 1996.

.. automodule:: QVideo.overlays.trackpy
   :members:
   :exclude-members: QTrackpyOverlay

.. autoclass:: QVideo.overlays.trackpy.QTrackpyOverlay
   :members:

YOLO
----

:class:`~QVideo.overlays.yolo.QYoloWidget` runs a
`YOLO <https://docs.ultralytics.com/>`_ object-detection model on each video
frame.  Detected bounding boxes and class labels are rendered in real time by
:class:`~QVideo.overlays.yolo.QYoloOverlay`.  The confidence threshold can be
adjusted from the widget; any model supported by the Ultralytics library can
be selected at construction time.

.. automodule:: QVideo.overlays.yolo
   :members:
   :exclude-members: QYoloOverlay

.. autoclass:: QVideo.overlays.yolo.QYoloOverlay
   :members:
