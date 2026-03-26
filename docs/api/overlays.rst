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
    widget.attachTo(screen)
    widget.newData.connect(my_slot)

Trackpy
-------

.. automodule:: QVideo.overlays.trackpy
   :members:
   :exclude-members: QTrackpyOverlay

.. autoclass:: QVideo.overlays.trackpy.QTrackpyOverlay
   :members:

YOLO
----

.. automodule:: QVideo.overlays.yolo
   :members:
   :exclude-members: QYoloOverlay

.. autoclass:: QVideo.overlays.yolo.QYoloOverlay
   :members:
