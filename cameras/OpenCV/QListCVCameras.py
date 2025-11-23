from QVideo.lib import QListCameras
from cv2_enumerate_cameras import enumerate_cameras
from QVideo.cameras.OpenCV.QOpenCVCamera import QOpenCVCamera


class QListCVCameras(QListCameras):
    '''A QComboBox that lists available OpenCV cameras.

    Inherits
    --------
    QVideo.lib.QListCameras
    '''

    def _model(self) -> type:
        return QOpenCVCamera

    def _listCameras(self) -> None:
        for c in enumerate_cameras():
            self.addItem(f'{c.name} (Index: {c.index})', c.index)


if __name__ == '__main__':
    QListCVCameras.example()
