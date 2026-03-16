from QVideo.lib import QListCameras
from QVideo.cameras.OpenCV.QOpenCVCamera import QOpenCVCamera

try:
    from cv2_enumerate_cameras import enumerate_cameras
except ImportError as e:
    raise ImportError(
        'cv2_enumerate_cameras is required for QListCVCameras. '
        'Install it with: pip install cv2-enumerate-cameras'
    ) from e


__all__ = ['QListCVCameras']


class QListCVCameras(QListCameras):

    '''A :class:`~pyqtgraph.Qt.QtWidgets.QComboBox` listing available OpenCV cameras.

    Enumerates connected camera devices using ``cv2_enumerate_cameras``
    and populates the combo box with their names and device indices.
    Selecting an entry provides the index needed to open the camera
    via :class:`~QVideo.cameras.OpenCV.QOpenCVCamera.QOpenCVCamera`.
    '''

    def _model(self) -> type:
        return QOpenCVCamera

    def _listCameras(self) -> None:
        for c in enumerate_cameras():
            self.addItem(f'{c.name} (Index: {c.index})', c.index)


if __name__ == '__main__':  # pragma: no cover
    QListCVCameras.example()
