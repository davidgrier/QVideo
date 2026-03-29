from pyqtgraph.Qt import QtCore
from QVideo.lib import QCameraTree
from QVideo.cameras.OpenCV import QOpenCVCamera


__all__ = ['QOpenCVTree']


class QOpenCVTree(QCameraTree):

    '''Camera control tree for :class:`~QVideo.cameras.OpenCV.QOpenCVCamera`.

    Extends :class:`~QVideo.lib.QCameraTree.QCameraTree` with a
    ``resolution`` dropdown populated from the formats reported by
    :class:`~QVideo.cameras.OpenCV._devices.QOpenCVDevices`.  Selecting an
    entry atomically updates width, height, and frame rate on the live
    device without stopping the video source.

    Width, height, and fps are displayed as read-only fields.  All format
    changes go through the ``resolution`` dropdown.

    When no format information is available (e.g. when
    :class:`~QtMultimedia.QMediaDevices` is absent and probing fails),
    the dropdown is omitted and the tree falls back to the standard
    read-only width/height display.

    Parameters
    ----------
    camera : QOpenCVCamera or None
        Camera instance to use.  If ``None``, a new
        :class:`~QVideo.cameras.OpenCV.QOpenCVCamera` is created from the
        keyword arguments below.
    cameraID : int
        Index of the camera device to open.  Used only when *camera* is
        ``None``.  Default: ``0``.
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
        super().__init__(camera, *args, **kwargs)
        for key in ('width', 'height'):
            if key in self._parameters:
                self._parameters[key].setOpts(enabled=False)
        # fps is controlled by the resolution dropdown when formats are known
        if self._hasFormats and 'fps' in self._parameters:
            self._parameters['fps'].setOpts(enabled=False)

    def _createTree(self, description=None) -> None:
        '''Build the parameter tree, prepending a resolution enum when formats
        are available.'''
        if description is None:
            description = self._defaultDescription(self.camera)
        formats = getattr(self.camera, '_formats', [])
        self._hasFormats = bool(formats)
        if formats:
            description = [self._formatEntry(formats)] + list(description)
        super()._createTree(description)

    def _formatEntry(self, formats: list) -> dict:
        '''Build the ``resolution`` list-parameter description dict.'''
        current_w = self.camera.width
        current_h = self.camera.height
        values: dict[str, tuple] = {}
        current_value = None
        for w, h, _min_fps, max_fps in formats:
            label = f'{w}\u00d7{h} @ {max_fps:.0f} Hz'
            val = (w, h, float(max_fps))
            values[label] = val
            if w == current_w and h == current_h and current_value is None:
                current_value = val
        if current_value is None:
            current_value = next(iter(values.values()))
        return {'name': 'resolution',
                'type': 'list',
                'limits': values,
                'value': current_value,
                'default': current_value}

    @QtCore.pyqtSlot(object, object)
    def _sync(self, root, changes) -> None:
        '''Handle parameter changes, routing ``resolution`` entries here.

        A ``resolution`` change is applied directly to the camera (width,
        height, fps) without going through the base-class ``camera.set``
        dispatch, since ``resolution`` is not a registered camera property.
        All other changes are forwarded to the base class.
        '''
        if self._ignoreSync:
            return
        fmt_value = None
        other = []
        for param, change, value in changes:
            if change == 'value' and param.name() == 'resolution':
                fmt_value = value
            else:
                other.append((param, change, value))
        if fmt_value is not None:
            w, h, fps = fmt_value
            self.camera.set('width', w)
            self.camera.set('height', h)
            self.camera.set('fps', fps)
            self._ignoreSync = True
            for key, val in self.camera.settings.items():
                self.set(key, val)
            self._ignoreSync = False
        if other:
            super()._sync(root, other)


if __name__ == '__main__':  # pragma: no cover
    QOpenCVTree.example()
