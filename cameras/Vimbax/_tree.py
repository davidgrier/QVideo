'''Camera property tree for Allied Vision VimbaX cameras.'''
from QVideo.cameras.Genicam import QGenicamTree
from QVideo.cameras.Vimbax import QVimbaXCamera


__all__ = ['QVimbaXTree']


class QVimbaXTree(QGenicamTree):

    '''Camera property tree for Allied Vision VimbaX cameras.

    Shows every node of the camera.  See
    :class:`~QVideo.cameras.Genicam.QGenicamTree` for the parameters.
    '''

    _cameraClass = QVimbaXCamera


if __name__ == '__main__':  # pragma: no cover
    QVimbaXTree.example()
