'''Camera property tree for GenICam cameras driven by viva-genicam.'''
from typing import ClassVar


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

    _DEFAULT_CONTROLS = (
        'ReverseX',
        'ReverseY',
        'AcquisitionFrameRate',
        'AcquisitionResultingFrameRate',
        'ExposureTime',
        'ExposureAuto',
        'Gain',
        'GainAuto',
        'GammaEnable',
        'Gamma',
        'BlackLevel',
        'PixelFormat',
        'Width',
        'Height',
        'OffsetX',
        'OffsetY',
    )

    #: Settings that the tree applies to the camera, those that the camera
    #: has.  Gamma is 1 and off, as scientific applications expect.  The
    #: frame rate is enabled, as in the trees of the vendors: while it is
    #: not, the camera makes the frame rate read-only and the tree shows
    #: no control that could enable it.  The exposure and the gain are
    #: manual: an automatic one changes under a measurement and, by
    #: lengthening the exposure, lowers the frame rate.
    _DEFAULT_SETTINGS: ClassVar[dict[str, object]] = dict(
        Gamma=1.0,
        GammaEnable=False,
        AcquisitionFrameRateEnable=True,
        ExposureAuto='Off',
        GainAuto='Off',
    )

    def __init__(self, *args,
                 camera: Source | None = None,
                 cameraID: int = 0,
                 controls: list[str] | None = None,
                 **kwargs) -> None:
        camera = camera or QVivaCamera(cameraID=cameraID)
        settings = {key: value
                    for key, value in self._DEFAULT_SETTINGS.items()
                    if key in camera.properties}
        if settings:
            camera.settings = settings
        controls = controls or self._DEFAULT_CONTROLS
        description = [entry for entry in self._defaultDescription(camera)
                       if entry['name'] in controls]
        super().__init__(camera, description, *args, **kwargs)
        camera.updateAccess()
        self._showAccess()

    def _showAccess(self) -> None:
        '''Enable the controls whose features the camera lets us write.

        The camera changes what is writable as its settings change (the
        exposure time while the exposure is automatic), so the controls
        follow it.  The camera has already looked at the shown features:
        its snapshot does so after a change in :meth:`_sync`, and it does so
        when it reports a change of its own.
        '''
        properties = self.camera.properties
        for key, param in self._parameters.items():
            if key in properties:
                param.setOpts(enabled=properties[key]['setter'] is not None)


if __name__ == '__main__':  # pragma: no cover
    QVivaTree.example()
