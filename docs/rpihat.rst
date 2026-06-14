Raspberry Pi AI Camera
======================

The `Raspberry Pi AI Camera`_ pairs Sony's IMX500 image sensor with an
on-chip neural-network accelerator.  The sensor runs inference
concurrently with video capture — at no host-CPU cost — by loading a
compiled network file (``.rpk``) onto the sensor at startup.

.. _Raspberry Pi AI Camera:
   https://www.raspberrypi.com/documentation/accessories/ai-camera.html

QVideo supports the AI Camera through
:class:`~QVideo.cameras.Picamera.QIMXCamera`, a subclass of
:class:`~QVideo.cameras.Picamera.QPicamera` that adds one extra signal:

.. code-block:: text

   QPicamera                   QIMXCamera
   ──────────────────────────  ──────────────────────────────────────
   newFrame (ndarray)          newFrame (ndarray)     ← inherited
   all picamera2 controls      all picamera2 controls ← inherited
                               newOutput (list|None)  ← new

:attr:`~QVideo.cameras.Picamera.QIMXCamera.newOutput` is emitted once
per frame.  Its payload is either a :class:`list` of
:class:`numpy.ndarray` objects (the raw tensor outputs produced by the
sensor's AI accelerator) or ``None`` when the sensor has not yet
produced results (typically the first few frames after start-up).

Installation
------------

Install picamera2 with IMX500 support on Raspberry Pi OS::

    pip install "picamera2[imx500]"

Then obtain a pre-compiled network (see `Model format`_ below).

Basic usage
-----------

.. code-block:: python

    from QVideo.cameras.Picamera import QIMXCamera, QIMXSource

    MODEL = (
        '/usr/share/imx500-models/'
        'imx500_network_nanodet_plus_416x416.rpk'
    )

    source = QIMXSource(model=MODEL)
    source.source.newOutput.connect(my_widget.setOutputs)
    source.start()

Because :class:`~QVideo.cameras.Picamera.QIMXCamera` is a full
:class:`~QVideo.cameras.Picamera.QPicamera` subclass, all standard
controls (exposure, gain, white balance, etc.) remain accessible
through :class:`~QVideo.cameras.Picamera.QPicameraTree` as usual.

Writing an inference consumer
-----------------------------

Connect :attr:`~QVideo.cameras.Picamera.QIMXCamera.newOutput` to a slot
that interprets the tensor list for the specific model loaded.  The slot
runs in the Qt main thread, so processing should be lightweight.  For
heavy post-processing, offload to a ``QThread`` or follow the same
drop-frame strategy used by
:class:`~QVideo.lib.VideoFilter.AsyncVideoFilter`.

The example below reads scores and bounding boxes from a NanoDet-Plus
model:

.. code-block:: python

    import numpy as np
    from qtpy import QtCore, QtWidgets


    class DetectionWidget(QtWidgets.QGroupBox):
        '''Display object-detection results from an IMX500 AI Camera.'''

        def __init__(self, parent=None) -> None:
            super().__init__('Detections', parent)
            self.setCheckable(True)
            self.setChecked(True)
            self._source = None

        @property
        def source(self):
            return self._source

        @source.setter
        def source(self, src) -> None:
            if self._source is not None:
                self._source.source.newOutput.disconnect(
                    self._setOutputs)
            self._source = src
            if src is not None:
                src.source.newOutput.connect(self._setOutputs)

        @QtCore.Slot(object)
        def _setOutputs(self, outputs) -> None:
            if outputs is None or not self.isChecked():
                return
            scores = outputs[0]    # model-specific layout
            boxes  = outputs[1]
            # ... update graphics items here

The tensor layout (which index holds scores, boxes, class IDs, etc.) is
model-specific.  Refer to the model's documentation or the ``picamera2``
examples for the correct interpretation.

Wiring into QCamcorder
----------------------

Subclass :class:`~QVideo.QCamcorder.QCamcorder` and add
:class:`DetectionWidget` alongside the camera tree:

.. code-block:: python

    from QVideo import QCamcorder
    from QVideo.cameras.Picamera import QIMXSource

    MODEL = (
        '/usr/share/imx500-models/'
        'imx500_network_nanodet_plus_416x416.rpk'
    )


    class AIDemo(QCamcorder):

        def __init__(self, source=None, parent=None) -> None:
            source = source or QIMXSource(model=MODEL)
            super().__init__(source, parent)
            self._detections = DetectionWidget(self)
            self._detections.source = source
            self._layout.addWidget(self._detections)


    if __name__ == '__main__':  # pragma: no cover
        import pyqtgraph as pg
        from qtpy import QtGui, QtWidgets

        app = pg.mkQApp('AIDemo')
        widget = AIDemo()
        QtWidgets.QShortcut(
            QtGui.QKeySequence('Ctrl+Q'), widget
        ).activated.connect(app.quit)
        widget.show()
        pg.exec()

Model format
------------

The IMX500 requires a packed-network file (``.rpk``) compiled for the
sensor's AI accelerator.  Sources:

* **Pre-built models** — installed to ``/usr/share/imx500-models/`` on
  Raspberry Pi OS via the ``imx500-all`` apt package.
* **Raspberry Pi model zoo** — available via the ``picamera2`` GitHub
  repository examples.
* **Custom models** — convert any supported ONNX or TFLite model with
  the IMX500 model-conversion tools provided by Sony.

.. note::

    :class:`~QVideo.cameras.Picamera.QIMXCamera` is intentionally
    excluded from the automatic camera-discovery backend registry
    because it requires a *model path* at construction time.  Create it
    directly rather than via :func:`~QVideo.lib.QCamera.Camera`.
