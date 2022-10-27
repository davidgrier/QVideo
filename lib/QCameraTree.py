from pyqtgraph.parametertree import (Parameter, ParameterTree)
from PyQt5.QtCore import (QThread, pyqtSignal, pyqtSlot, pyqtProperty)
from PyQt5.QtWidgets import QHeaderView
from QVideo.lib.QVideoCamera import QVideoCamera
import logging


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class QCameraTree(ParameterTree):

    valueChanged = pyqtSignal(str, object)

    controls = [
        {'name': 'Shape', 'type': 'group', 'children': [
            {'name': 'Width', 'type': 'int', 'value': 640},
            {'name': 'Height', 'type': 'int', 'value': 480}]},
        {'name': 'FPS', 'type': 'float', 'value': 0., 'readonly': True}
    ]

    @staticmethod
    def _parseDescription(param):
        d = dict()
        if param.hasChildren():
            for p in param.children():
                d.update(QCameraTree._parseDescription(p))
        else:
            d.update({param.name().lower(): param})
        return d

    def __init__(self, camera, controls, *args, **kwargs):
        super().__init__(*args, **kwargs)
        controls = [*controls, *QCameraTree.controls]
        self._setupUi(controls)
        self.camera = camera
        self._connectSignals()
        self.setMinimumWidth(250)
        self.header().setSectionResizeMode(0, QHeaderView.Fixed)
        self.setColumnWidth(0, 150)

    def _setupUi(self, c):
        self._p = Parameter.create(name='params', type='group', children=c)
        self.setParameters(self._p, showTop=False)
        self._parameters = self._parseDescription(self._p)

    def _connectSignals(self):
        self._p.sigTreeStateChanged.connect(self._handleChanges)
        self.valueChanged.connect(self._camera.set)
        self._camera.meter.fpsReady.connect(
            lambda fps: self.set('fps', fps, updateCamera=False))

    @pyqtSlot(object, object)
    def _handleChanges(self, tree, changes):
        if not self._updateCamera:
            return
        for param, change, value in changes:
            if (change == 'value'):
                key = param.name().lower()
                self.valueChanged.emit(key, value)
                logger.debug(f'Change {key}: {value}')

    def set(self, key, value, updateCamera=True):
        self._updateCamera = updateCamera
        if key in self._parameters:
            logger.debug(f'set {key}: {value}')
            self._parameters[key].setValue(value)
        else:
            logger.warning(f'Unsupported property: {key}')
        self._updateCamera = True

    @pyqtProperty(QVideoCamera)
    def camera(self):
        return self._camera

    @camera.setter
    def camera(self, camera):
        self._camera = camera
        if camera is None:
            return
        if not isinstance(camera, QVideoCamera):
            logger.error(f'unsupported camera of type {type(camera)}')
            return
        for p in camera.properties():
            self.set(p, camera.get(p), updateCamera=False)
        self._thread = QThread()
        camera.moveToThread(self._thread)
        self._thread.started.connect(camera.start)
        self._thread.finished.connect(camera.close)
        self._thread.start(QThread.TimeCriticalPriority)

    @pyqtSlot()
    def close(self):
        self._thread.quit()
        self._thread.wait()
        self.camera = None
