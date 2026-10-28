'''FLIR camera backend via the Spinnaker GenTL producer.

Supports FLIR (formerly Point Grey) USB3 Vision and GigE Vision cameras
through `Spinnaker <https://www.flir.com/products/spinnaker-sdk/>`_,
FLIR's machine-vision SDK.  The Spinnaker installer registers the
GenTL producer path in ``GENICAM_GENTL64_PATH``.

.. note::

    Spinnaker GenTL producer 4.3.0.189 hangs in ``DevClose()`` when the
    camera is released, which blocks application exit.  The bug is fixed
    in Spinnaker 4.4.0.

QVideo does not use PySpin, Spinnaker's own Python wrapper.  The GenTL
route reaches the camera's whole node map, register nodes included, and
gives the hardware timestamp of each frame, with nothing beyond the SDK.
PySpin is a separate binary download built only for Python 3.12 and
earlier, and it fails on later versions.

Classes
-------
QFlirCamera
    Camera backed by a FLIR device via the Spinnaker GenTL producer.
QFlirSource
    Threaded video source backed by :class:`QFlirCamera`.
QFlirTree
    Parameter tree widget for :class:`QFlirCamera` controls.
'''
from ._camera import QFlirCamera, QFlirSource
from ._tree import QFlirTree


__all__ = 'QFlirCamera QFlirSource QFlirTree'.split()
