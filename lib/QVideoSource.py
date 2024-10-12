from PyQt5.QtCore import (QThread, pyqtSlot)
from QVideo.lib import QVideoCamera


class QVideoSource(QThread):
    def __init__(self, camera: QVideoCamera) -> None:
        super().__init__()
        self.camera = camera
        self.camera.moveToThread(self)
        self.started.connect(self.camera.start)
        self.finished.connect(self.camera.close)
        super().start(QThread.TimeCriticalPriority)

    def __del__(self):
        self.quit()
        self.wait()
        self.camera = None

    @pyqtSlot()
    def start(self):
        self.camera.start()
        return self

    @pyqtSlot()
    def stop(self) -> None:
        self.camera.stop()

    @pyqtSlot()
    def close(self) -> None:
        self.__del__()
