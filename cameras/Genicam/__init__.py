'''Generic GenICam camera backend via Harvesters.

Provides an abstract base for any camera that implements the
`GenICam <https://www.emva.org/standards-technology/genicam/>`_
standard and is accessible via a GenTL producer ``.cti`` file.
Camera vendors supply manufacturer-specific producer files; concrete
subclasses set the :attr:`~QGenicamCamera.producer` class attribute
to the appropriate path.

Requires the ``genicam`` and ``harvesters`` packages::

    pip install genicam harvesters

If a camera of this family cannot be opened, ``python -m
QVideo.cameras.gentl`` (see :mod:`QVideo.cameras.gentl`) diagnoses the
Python packages, the ``GENICAM_GENTL64_PATH`` variable and the producer
file.  It is a module of its own because it must run when the packages
above are missing.

Classes
-------
QGenicamCamera
    Abstract base for GenICam cameras accessed via Harvesters.
QGenicamTree
    Parameter tree widget for :class:`QGenicamCamera` controls.
'''
from ._camera import QGenicamCamera
from ._tree import QGenicamTree
from QVideo.cameras._deprecated import deprecated_sources

# Tell Sphinx that these classes belong to the public package namespace,
# not the private _camera / _tree submodules, to avoid duplicate
# object descriptions in the generated docs.
QGenicamCamera.__module__ = __name__
QGenicamTree.__module__ = __name__

#: The retired ``Q<Name>Source`` classes, until the next major release.
__getattr__ = deprecated_sources(__name__, QGenicamSource=QGenicamCamera)

__all__ = 'QGenicamCamera QGenicamTree'.split()
