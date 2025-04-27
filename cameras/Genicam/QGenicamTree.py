from PyQt5.QtCore import pyqtProperty
from QVideo.lib import QCameraTree
from QVideo.cameras.Genicam import QGenicamCamera
from genicam.genapi import EVisibility


class QGenicamTree(QCameraTree):

    def __init__(self, *args,
                 camera: QCameraTree.Source | None = None,
                 visibility: EVisibility = EVisibility.Beginner,
                 controls: list[str] | None = None,
                 **kwargs) -> None:
        camera = camera or QGenicamCamera(*args, **kwargs)
        if controls is not None:
            visibility = EVisibility.Guru
        description = camera.description(controls=controls)
        super().__init__(camera, description, *args, **kwargs)
        self.visibility = visibility
        self._updateEnabled()

    def _connectSignals(self) -> None:
        super()._connectSignals()
        for item in self.listAllItems():
            p = item.param
            p.sigValueChanged.connect(self._changeHandler)

    def _changeHandler(self, *args) -> None:
        self._updateEnabled()

    def _updateVisible(self) -> None:
        for item in self.listAllItems()[1:]:
            p = item.param
            visibility = p.opts.get('visibility', EVisibility.Guru)
            visible = visibility <= self.visibility
            if p.opts['type'] in ('action', None):
                visible = False
            p.setOpts(visible=visible)

    def _updateEnabled(self) -> None:
        properties = self.camera.properties()
        for item in self.listAllItems()[1:]:
            p = item.param
            if p.opts.get('visible', False):
                name = p.opts['name']
                enabled = name in properties
                p.setOpts(enabled=enabled)

    @pyqtProperty(object)
    def visibility(self) -> EVisibility:
        return self._visibility

    @visibility.setter
    def visibility(self, visibility: EVisibility) -> None:
        self._visibility = visibility
        self._updateVisible()


if __name__ == '__main__':
    QGenicamTree.example()
