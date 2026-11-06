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

Recording the overlays
----------------------

Overlays are drawn by the screen, so a recorder connected to the camera does
not see them.  To record what the screen shows, set
:attr:`~QVideo.lib.QVideoScreen.QVideoScreen.composite` to ``True`` and
record from the screen: its ``newFrame`` signal then carries the rendered
scene (the video frame with the overlays on it) as an ``(H, W, 3)`` RGB
array, instead of the frame.  The rendering costs time on the interface
thread, so it suits a demonstration or a figure better than a measurement.
:mod:`QVideo.demos.compositedemo` shows the wiring, with a menu that chooses
what the recorder records.

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

Two things can run the network.  ``ultralytics`` loads a ``.pt`` file and
uses a GPU if ``torch`` finds one.  OpenCV loads an ``.onnx`` file and
needs nothing but QVideo, but it runs on the CPU: the ``opencv-python``
wheels have no CUDA support.  The default (``backend='auto'``) picks OpenCV
for a file that ends in ``.onnx`` and ``ultralytics`` for anything else::

    widget = QYoloWidget(parent, model_name='yolo11n.onnx')   # OpenCV
    widget = QYoloWidget(parent, model_name='yolo11n.pt')     # ultralytics

*Preparing an ONNX file.*  QVideo does not ship a model.  Ultralytics
licenses its pretrained weights, and files exported from them, under the
AGPL-3.0, which can bind the program that uses them; read
`their terms <https://www.ultralytics.com/license>`_, or use a model
whose license suits your work.  To export a model that you may use, on a
machine that has ``ultralytics`` (``torch`` is needed for this step only,
not to run the file)::

    from ultralytics import YOLO
    YOLO('my_weights.pt').export(format='onnx', imgsz=640)

The reader expects the export of a YOLOv8 or later detection model, whose
output has the shape ``(1, 4 + classes, N)``: the center and size of each
box, then a score for each class.  It does not read the older YOLOv5 layout
with a separate objectness, nor an export that has non-maximum suppression
in the network.  Give ``imgsz`` the size of the export, and ``names`` the
names of your classes (a list), unless the network has the 80 classes of
COCO, whose names are the default.  Without names, a detection is labeled
with the number of its class.

.. note::

    The reader has been tested against the exports of ``yolo11n.pt`` and
    ``yolo26n.pt`` by Ultralytics 8.4, with default options: it finds the objects that ``ultralytics`` finds, with
    the same labels, and the boxes differ by a few pixels (OpenCV is given a
    square, padded input).  Other exports are expected to work if they have
    the layout above.  If one does not read, ``QYoloWidget`` logs the
    reason and shows no boxes.

    Importing ``ultralytics`` makes OpenCV use one thread for the whole
    program, which makes the ONNX model about four times slower.  QVideo
    imports it only for a ``.pt`` model, and puts the number of threads
    back.  A program of your own that imports it first should do the same
    (``cv2.setNumThreads(n)``).

.. automodule:: QVideo.overlays.yolo
   :members:
   :exclude-members: QYoloOverlay

.. autoclass:: QVideo.overlays.yolo.QYoloOverlay
   :members:
