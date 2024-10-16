from pyqtgraph.parametertree import (Parameter, ParameterTree)
from PyQt5.QtCore import (pyqtSignal, pyqtSlot, pyqtProperty, Qt)
from PyQt5.QtWidgets import QHeaderView
from QVideo.lib import (QCamera, QVideoSource)
from typing import (TypeAlias, Optional, Union, Tuple, List, Dict)
import logging


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


Source: TypeAlias = Union[QCamera, QVideoSource]
Description: TypeAlias = List[Dict[str, str]]
Value: TypeAlias = Union[bool, int, float, str]
Change: TypeAlias = Tuple[Parameter, str, Value]
Changes: TypeAlias = List[Change]


class QCameraTree(ParameterTree):

    @staticmethod
    def _getParameters(parameter: Parameter) -> None:
        '''Recursively find setters for named Parameters'''
        parameters = dict()
        if parameter.hasChildren():
            for p in parameter.children():
                parameters.update(QCameraTree._getParameters(p))
        else:
            name = parameter.name().lower()
            parameters.update({name: parameter})
        return parameters

    @staticmethod
    def _defaultDescription(camera: QCamera) -> List:
        settings = camera.settings().items()
        entries = [{'name': key,
                    'type': value.__class__.__name__,
                    'value': value}
                   for key, value in settings if value is not None]
        return [{'name': camera.name,
                 'type': 'group',
                 'children': entries}]

    def __init__(self,
                 source: Source,
                 description: Optional[Description],
                 *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setSource(source)
        self._createTree(description)
        self._connectSignals()
        self._setupUi()

    def _setupUi(self) -> None:
        self.setMinimumWidth(250)
        self.header().setSectionResizeMode(0, QHeaderView.Fixed)
        self.setColumnWidth(0, 150)

    def _createTree(self, description: Optional[Description]) -> None:
        if description is None:
            description = self._defaultDescription(self.camera)
        self._tree = Parameter.create(name=self.camera.name, type='group',
                                      children=description)
        self.setParameters(self._tree, showTop=False)
        self._parameters = self._getParameters(self._tree)
        for name, parameter in self._parameters.items():
            parameter.setValue(self.camera.get(name))

    def _connectSignals(self) -> None:
        self._tree.sigTreeStateChanged.connect(self._sync)

    @pyqtSlot(object, object)
    def _sync(self, tree: ParameterTree, changes: Changes) -> None:
        for param, change, value in changes:
            if (change == 'value'):
                key = param.name().lower()
                logger.debug(f'Syncing {key}: {change}: {value}')
                self.camera.set(key, value)

    def set(self, key: str, value: Value) -> None:
        if key in self._parameters:
            logger.debug(f'set {key}: {value}')
            self._parameters[key].setValue(value)
        else:
            logger.warning(f'Unsupported property: {key}')

    def setSource(self, source: Source) -> None:
        if isinstance(source, QVideoSource):
            self._source = source
            self._camera = source.camera
        elif isinstance(source, QCamera):
            self._camera = source
            self._source = QVideoSource(self._camera)
        else:
            logger.error(f'Unsupported video source: {source}')

    @pyqtProperty(QVideoSource)
    def source(self) -> QVideoSource:
        return self._source

    @pyqtProperty(QCamera)
    def camera(self) -> QCamera:
        return self._camera

    @pyqtSlot()
    def start(self):
        self.source.start()
        return self

    @pyqtSlot()
    def stop(self) -> None:
        self.source.stop()

    @pyqtSlot()
    def close(self) -> None:
        self.stop()
