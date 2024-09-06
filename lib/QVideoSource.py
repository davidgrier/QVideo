from PyQt5.QtCore import (QThread, pyqtSlot)
from QVideo.lib import QVideoCamera


class QVideoSource(QThread):
    def __init__(self, camera: QVideoCamera) -> None:
        super().__init__()
        self.camera = camera
        self.camera.moveToThread(self)
        self.started.connect(self.camera.start)
        self.finished.connect(self.camera.close)

    @pyqtSlot()
    def start(self) -> None:
        super().start(QThread.TimeCriticalPriority)

    @pyqtSlot()
    def close(self) -> None:
        self.quit()
        self.wait()
        self.camera = None
