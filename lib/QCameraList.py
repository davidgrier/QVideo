from pyqtgraph.Qt import QComboBox


class QCameraList(QComboBox):
    def __init__(self, parent=None):
        super(QCameraList, self).__init__(parent)
        self.refresh()

    def refresh(self):
        from pyqtgraph.camera import listCameras

        self.clear()
        cameras = listCameras()
        for cam in cameras:
            self.addItem(cam['name'], cam)
