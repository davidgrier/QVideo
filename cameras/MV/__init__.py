'''Universal GenICam backend via the MATRIX VISION mvGenTLProducer.

Supports any GenICam-compliant camera through the free
`mvGenTLProducer
<https://www.matrix-vision.com/software-support.html>`_
universal GenTL producer from MATRIX VISION.  Installing the
mvIMPACT SDK registers the producer path in ``GENICAM_GENTL64_PATH``.

.. note::

    FLIR/Spinnaker cameras are not supported by this backend.
    Use :mod:`QVideo.cameras.Flir` for FLIR cameras.

Classes
-------
QMVCamera
    Camera backed by any GenICam device via the mvGenTLProducer.
QMVSource
    Threaded video source backed by :class:`QMVCamera`.
QMVTree
    Parameter tree widget for :class:`QMVCamera` controls.
'''
from ._camera import QMVCamera, QMVSource
from ._tree import QMVTree


__all__ = 'QMVCamera QMVSource QMVTree'.split()
