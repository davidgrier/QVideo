from QVideo.lib import QCameraTree
from QVideo.lib.resolutions import probe_resolutions
from QVideo.cameras.OpenCV import QOpenCVCamera
from pyqtgraph.Qt import QtCore


__all__ = ['QOpenCVResolutionTree']


class QOpenCVResolutionTree(QCameraTree):

    '''Camera tree for :class:`~QVideo.cameras.OpenCV.QOpenCVCamera.QOpenCVCamera`
    with a resolution drop-down selector.

    Extends :class:`~QVideo.lib.QCameraTree.QCameraTree` with resolution
    awareness: when the camera supports more than one resolution, the
    separate ``width`` and ``height`` spinboxes are replaced by a single
    ``resolution`` drop-down whose entries are the ``(width, height)``
    pairs accepted by the hardware (displayed as ``"W×H"`` strings).
    When only one resolution is available the tree behaves identically
    to :class:`~QVideo.cameras.OpenCV.QOpenCVTree.QOpenCVTree`.

    Parameters
    ----------
    camera : QOpenCVCamera or None
        Camera instance to use.  If ``None``, a new
        :class:`~QVideo.cameras.OpenCV.QOpenCVCamera.QOpenCVCamera` is
        created from the camera keyword arguments below.
    cameraID : int
        Index of the camera device to open.  Used only when *camera*
        is ``None``.  Default: ``0``.
    mirrored : bool
        Flip the image horizontally.  Used only when *camera* is ``None``.
        Default: ``False``.
    flipped : bool
        Flip the image vertically.  Used only when *camera* is ``None``.
        Default: ``False``.
    gray : bool
        Open in grayscale mode.  Used only when *camera* is ``None``.
        Default: ``False``.
    *args :
        Positional arguments forwarded to
        :class:`~QVideo.lib.QCameraTree.QCameraTree`.
    **kwargs :
        Keyword arguments forwarded to
        :class:`~QVideo.lib.QCameraTree.QCameraTree`.
    '''

    def __init__(self, *args,
                 camera: QOpenCVCamera | None = None,
                 cameraID: int = 0,
                 mirrored: bool = False,
                 flipped: bool = False,
                 gray: bool = False,
                 **kwargs) -> None:
        if camera is None:
            camera = QOpenCVCamera(cameraID=cameraID,
                                   mirrored=mirrored,
                                   flipped=flipped,
                                   gray=gray)
        resolutions = probe_resolutions(camera.device)
        self._resolutions = resolutions
        self._resolutionMap = {f'{w}\u00d7{h}': (w, h) for w, h in resolutions}
        description = (self._resolutionDescription(camera, resolutions)
                       if len(resolutions) > 1 else None)
        super().__init__(camera, *args, description=description, **kwargs)

    @staticmethod
    def _resolutionDescription(camera: QOpenCVCamera,
                               resolutions: list) -> list:
        '''Build a parameter-tree description with a resolution selector.

        Replaces the ``width`` and ``height`` entries in the default
        description with a single ``resolution`` list parameter whose
        display strings are formatted as ``"W×H"``.

        Parameters
        ----------
        camera : QOpenCVCamera
            Open camera whose current resolution seeds the selector.
        resolutions : list[tuple[int, int]]
            Sorted list of ``(width, height)`` pairs to offer.

        Returns
        -------
        list[dict]
            Parameter-tree description ready for
            :class:`~pyqtgraph.parametertree.Parameter`.
        '''
        description = QCameraTree._defaultDescription(camera)
        insert_index = next(
            (i for i, e in enumerate(description) if e['name'] == 'width'),
            None)
        description = [e for e in description
                       if e['name'] not in ('width', 'height')]
        current = (camera.width, camera.height)
        if current not in resolutions:
            current = resolutions[0]
        current_str = f'{current[0]}\u00d7{current[1]}'
        limits = [f'{w}\u00d7{h}' for w, h in resolutions]
        entry = {'name': 'resolution',
                 'type': 'list',
                 'limits': limits,
                 'value': current_str,
                 'default': current_str}
        if insert_index is not None:
            description.insert(insert_index, entry)
        else:
            description.append(entry)
        return description

    @QtCore.pyqtSlot(object, object)
    def _sync(self, root, changes) -> None:
        if self._ignoreSync:
            return
        for param, change, value in changes:
            if change == 'value' and param.name() == 'resolution':
                if value in self._resolutionMap:
                    w, h = self._resolutionMap[value]
                    fps = (self.camera.fps
                           if 'fps' in self.camera._properties else None)
                    self.camera.set('width', w)
                    self.camera.set('height', h)
                    if fps is not None:
                        self.camera.set('fps', fps)
                return
        super()._sync(root, changes)

    @QtCore.pyqtSlot(str, object)
    def set(self, key: str, value) -> None:
        '''Set a camera property and update the tree.

        When the tree shows a ``resolution`` selector, ``width`` and
        ``height`` updates are redirected to that selector rather than
        to individual spinboxes.

        Parameters
        ----------
        key : str
            Property name.
        value :
            New value (ignored for ``width``/``height`` when in
            resolution-selector mode; the current camera state is read
            instead).
        '''
        if key in ('width', 'height') and 'resolution' in self._parameters:
            res_str = f'{self.camera.width}\u00d7{self.camera.height}'
            if res_str in self._resolutionMap:
                self._parameters['resolution'].setValue(res_str)
        else:
            super().set(key, value)


if __name__ == '__main__':  # pragma: no cover
    QOpenCVResolutionTree.example()
