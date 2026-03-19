from QVideo.lib import QCameraTree
from QVideo.cameras.Noise import QNoiseSource


__all__ = ['QNoiseTree']


class QNoiseTree(QCameraTree):

    '''Camera tree for a :class:`~QVideo.cameras.Noise.QNoiseCamera.QNoiseCamera`.

    Convenience subclass of :class:`~QVideo.lib.QCameraTree.QCameraTree`
    that creates and opens a :class:`~QVideo.cameras.Noise.QNoiseSource.QNoiseSource`
    automatically.

    Parameters
    ----------
    cameraID : int
        Accepted for API consistency with other camera trees; ignored.
    *args :
        Positional arguments forwarded to
        :class:`~QVideo.lib.QCameraTree.QCameraTree`.
    **kwargs :
        Keyword arguments forwarded to
        :class:`~QVideo.lib.QCameraTree.QCameraTree`.
    '''

    def __init__(self, *args, cameraID: int = 0, **kwargs) -> None:
        super().__init__(QNoiseSource(), *args, **kwargs)
        if 'color' in self._parameters:
            self._parameters['color'].setOpts(enabled=False)


if __name__ == '__main__':  # pragma: no cover
    QNoiseTree.example()
