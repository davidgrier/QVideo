from QVideo.lib import QCameraTree
from QVideo.cameras.Noise import QNoiseCamera, QNoiseSource


__all__ = ['QNoiseTree']


class QNoiseTree(QCameraTree):

    '''Camera tree for a
    :class:`~QVideo.cameras.Noise.QNoiseCamera.QNoiseCamera`.

    Convenience subclass of :class:`~QVideo.lib.QCameraTree.QCameraTree`
    that creates and opens a
    :class:`~QVideo.cameras.Noise.QNoiseSource.QNoiseSource` automatically.

    Parameters
    ----------
    camera : QNoiseCamera or None
        Camera instance to use.  If ``None``, a new
        :class:`~QVideo.cameras.Noise.QNoiseCamera.QNoiseCamera` is created.
    cameraID : int
        Accepted for API consistency with other camera trees; ignored when
        *camera* is provided.
    *args :
        Positional arguments forwarded to
        :class:`~QVideo.lib.QCameraTree.QCameraTree`.
    **kwargs :
        Keyword arguments forwarded to
        :class:`~QVideo.lib.QCameraTree.QCameraTree`.
    '''

    def __init__(self, *args,
                 camera: QNoiseCamera | None = None,
                 cameraID: int = 0,
                 **kwargs) -> None:
        source = QNoiseSource(camera=camera)
        super().__init__(source, *args, **kwargs)
        if 'color' in self._parameters:
            self._parameters['color'].setOpts(enabled=False)


if __name__ == '__main__':  # pragma: no cover
    QNoiseTree.example()
