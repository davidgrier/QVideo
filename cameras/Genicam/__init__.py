from ._camera import QGenicamCamera, QGenicamSource
from ._tree import QGenicamTree

# Tell Sphinx that these classes belong to the public package namespace,
# not the private _camera / _tree submodules, to avoid duplicate
# object descriptions in the generated docs.
QGenicamCamera.__module__ = __name__
QGenicamSource.__module__ = __name__
QGenicamTree.__module__ = __name__

__all__ = 'QGenicamCamera QGenicamSource QGenicamTree'.split()
