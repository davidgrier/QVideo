from pyqtgraph.parametertree import (Parameter, ParameterTree)
from PyQt5.QtCore import (pyqtSignal, pyqtSlot, pyqtProperty)
from PyQt5.QtWidgets import QHeaderView
from QVideo.lib.QVideoCamera import QVideoCamera
from QVideo.lib.QVideoSource import QVideoSource
from typing import (Optional, Union, Tuple, List, Dict, Any)
import logging


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class QCameraTree(ParameterTree):

    valueChanged = pyqtSignal(str, object)

    @staticmethod
    def _parseDescription(param: Parameter) -> Dict:
        d = dict()
        if param.hasChildren():
            for p in param.children():
                d.update(QCameraTree._parseDescription(p))
        else:
            d.update({param.name().lower(): param})
        return d

    def __init__(self,
                 camera: Optional[QVideoCamera] = None,
                 controls: Optional[List] = None,
                 *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._setupUi()
        self._setupTree(controls or camera)
        self.camera = camera
        self._connectSignals()

    def __del__(self):
        if isinstance(self.source, QVideoSource):
            self.source.close()

    def _setupUi(self) -> None:
        self.setMinimumWidth(250)
        self.header().setSectionResizeMode(0, QHeaderView.Fixed)
        self.setColumnWidth(0, 150)

    @staticmethod
    def _controls(camera: Optional[QVideoCamera]) -> List:
        if camera is None:
            clist = list()
        else:
            clist = [{'name': key,
                      'type': value.__class__.__name__,
                      'value': value}
                     for key, value in camera.settings().items()
                     if value is not None]
        return [{'name': 'Controls',
                 'type': 'group',
                 'children': clist}]

    def _setupTree(self, c: Union[List, QVideoCamera]) -> None:
        c = c if isinstance(c, list) else self._controls(c)
        self._p = Parameter.create(name='params', type='group', children=c)
        self.setParameters(self._p, showTop=False)
        self._parameters = self._parseDescription(self._p)

    def _connectSignals(self) -> None:
        self._p.sigTreeStateChanged.connect(self._handleChanges)
        self.valueChanged.connect(self._camera.set)
        self._camera.meter.fpsReady.connect(
            lambda fps: self.set('fps', fps, updateCamera=False))

    @pyqtSlot(object, object)
    def _handleChanges(self,
                       tree: ParameterTree,
                       changes: List[Tuple]) -> None:
        if not self._updateCamera:
            return
        for param, change, value in changes:
            if (change == 'value'):
                key = param.name().lower()
                self.valueChanged.emit(key, value)
                logger.debug(f'Change {key}: {value}')

    def set(self, key: str, value: Any, updateCamera: bool = True) -> None:
        self._updateCamera = updateCamera
        if key in self._parameters:
            logger.debug(f'set {key}: {value}')
            self._parameters[key].setValue(value)
        else:
            logger.warning(f'Unsupported property: {key}')
        self._updateCamera = True

    @pyqtProperty(QVideoCamera)
    def camera(self) -> QVideoCamera:
        return self._camera

    @camera.setter
    def camera(self, camera: Optional[QVideoCamera]) -> None:
        self._camera = camera
        if camera is None:
            self._source = None
            return
        if not isinstance(camera, QVideoCamera):
            logger.error(f'unsupported camera of type {type(camera)}')
            return
        for p in camera.properties():
            self.set(p, camera.get(p), updateCamera=False)
        self._source = QVideoSource(camera)

    @pyqtProperty(QVideoSource)
    def source(self) -> QVideoSource:
        return self._source

    @source.setter
    def source(self, source: QVideoSource) -> None:
        self._source = source
        self._camera = self._source.camera

    def start(self):
        self.source.start()
        return self

    @pyqtSlot()
    def close(self) -> None:
        self.__del__()
