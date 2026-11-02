'''GenICam cameras through viva-genicam, with no GenTL producer.

`viva-genicam <https://github.com/VitalyVorobyev/viva-genicam>`_ is a
GenICam stack written in Rust that speaks USB3 Vision and GigE Vision
itself.  It needs no vendor SDK and no ``.cti`` file, and it releases the
interpreter lock while it waits for a frame.

Requires the ``viva-genicam`` package::

    pip install viva-genicam

Classes
-------
QVivaCamera
    GenICam camera on USB3 Vision or GigE Vision.
QVivaSource
    Threaded video source backed by :class:`QVivaCamera`.
QVivaTree
    Parameter tree widget for :class:`QVivaCamera` controls.
'''
from ._camera import QVivaCamera, QVivaSource
from ._tree import QVivaTree

# Tell Sphinx that these classes belong to the public package namespace,
# not the private _camera / _tree submodules.
QVivaCamera.__module__ = __name__
QVivaSource.__module__ = __name__
QVivaTree.__module__ = __name__

__all__ = 'QVivaCamera QVivaSource QVivaTree'.split()
