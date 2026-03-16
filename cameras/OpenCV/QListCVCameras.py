import warnings
import cv2
from QVideo.lib import QListCameras
from QVideo.cameras.OpenCV.QOpenCVCamera import QOpenCVCamera

try:
    from cv2_enumerate_cameras import enumerate_cameras as _enumerate_cameras
except ImportError:
    warnings.warn(
        'cv2-enumerate-cameras is not installed; '
        'falling back to device probing. Camera names will be generic. ',
        ImportWarning,
        stacklevel=2,
    )
    _enumerate_cameras = None


__all__ = ['QListCVCameras']

_MAX_PROBE = 10


def _probe_cameras():
    '''Probe VideoCapture indices 0.._MAX_PROBE-1 using pure cv2.

    Yields (label, index) pairs for each index that opens successfully.
    Camera labels are synthetic, e.g. ``"Camera 0 (640x480)"``.
    OpenCV log output is suppressed during probing.
    '''
    level = cv2.getLogLevel()
    cv2.setLogLevel(0)
    try:
        for i in range(_MAX_PROBE):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                yield f'Camera {i} ({w}x{h})', i
            cap.release()
    finally:
        cv2.setLogLevel(level)


class QListCVCameras(QListCameras):

    '''A :class:`~pyqtgraph.Qt.QtWidgets.QComboBox` listing available OpenCV cameras.

    If ``cv2-enumerate-cameras`` is installed, devices are listed
    with their real names and indices via
    :func:`cv2_enumerate_cameras.enumerate_cameras`.
    Otherwise, a probe-based fallback scans indices 0–9 using
    :func:`cv2.VideoCapture` and generates synthetic labels such as
    ``"Camera 0 (640x480)"``.

    Inherits
    --------
    QVideo.lib.QListCameras
    '''

    def _model(self) -> type:
        return QOpenCVCamera

    def _listCameras(self) -> None:
        if _enumerate_cameras is not None:
            for c in _enumerate_cameras():
                self.addItem(f'{c.name} (Index: {c.index})', c.index)
        else:
            for name, index in _probe_cameras():
                self.addItem(name, index)


if __name__ == '__main__':  # pragma: no cover
    QListCVCameras.example()
