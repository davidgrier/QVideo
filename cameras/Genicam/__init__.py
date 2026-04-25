'''Generic GenICam camera backend via Harvesters.

Provides an abstract base for any camera that implements the
`GenICam <https://www.emva.org/standards-technology/genicam/>`_
standard and is accessible via a GenTL producer ``.cti`` file.
Camera vendors supply manufacturer-specific producer files; concrete
subclasses set the :attr:`~QGenicamCamera.producer` class attribute
to the appropriate path.

Requires the ``genicam`` and ``harvesters`` packages::

    pip install genicam harvesters

Classes
-------
QGenicamCamera
    Abstract base for GenICam cameras accessed via Harvesters.
QGenicamSource
    Threaded video source backed by :class:`QGenicamCamera`.
QGenicamTree
    Parameter tree widget for :class:`QGenicamCamera` controls.
'''
from ._camera import QGenicamCamera, QGenicamSource
from ._tree import QGenicamTree

# Tell Sphinx that these classes belong to the public package namespace,
# not the private _camera / _tree submodules, to avoid duplicate
# object descriptions in the generated docs.
QGenicamCamera.__module__ = __name__
QGenicamSource.__module__ = __name__
QGenicamTree.__module__ = __name__

__all__ = 'QGenicamCamera QGenicamSource QGenicamTree'.split()
