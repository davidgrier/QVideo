'''Camera property tree for GenICam cameras driven by viva-genicam.'''
from QVideo.cameras.Viva._camera import QVivaCamera
from QVideo.lib.QCameraTree import QCameraTree, Source


__all__ = ['QVivaTree']


class QVivaTree(QCameraTree):

    '''Camera property tree for :class:`~QVideo.cameras.Viva.QVivaCamera`.

    Shows a curated set of controls, those of :attr:`_DEFAULT_CONTROLS`
    that the camera has, in a flat list.

    Parameters
    ----------
    camera : QVivaCamera or None
        Camera instance to use.  If ``None``, a new :class:`QVivaCamera`
        is created from ``cameraID``.
    cameraID : int
        Index of the camera to open.  Used only when *camera* is
        ``None``.  Default: ``0``.
    controls : list of str or None
        Names of the GenICam features to show.  Default:
        :attr:`_DEFAULT_CONTROLS`.  ``list(camera.properties)`` shows them
        all.
    '''

    _DEFAULT_CONTROLS = [
        'ReverseX',
        'ReverseY',
        'AcquisitionFrameRate',
        'AcquisitionResultingFrameRate',
        'ExposureTime',
        'ExposureAuto',
        'Gain',
        'GainAuto',
        'Gamma',
        'BlackLevel',
        'PixelFormat',
        'Width',
        'Height',
        'OffsetX',
        'OffsetY',
    ]

    def __init__(self, *args,
                 camera: Source | None = None,
                 cameraID: int = 0,
                 controls: list[str] | None = None,
                 **kwargs) -> None:
        camera = camera or QVivaCamera(cameraID=cameraID)
        controls = controls or self._DEFAULT_CONTROLS
        description = [entry for entry in self._defaultDescription(camera)
                       if entry['name'] in controls]
        super().__init__(camera, description, *args, **kwargs)


if __name__ == '__main__':  # pragma: no cover
    QVivaTree.example()
