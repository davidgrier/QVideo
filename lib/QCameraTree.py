from pyqtgraph.parametertree import (Parameter, ParameterTree)
from PyQt5.QtCore import (pyqtSlot, pyqtProperty)
from PyQt5.QtWidgets import QHeaderView
from QVideo.lib import (QCamera, QVideoSource)
from typing import TypeAlias
import logging


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class QCameraTree(ParameterTree):

    Source: TypeAlias = QCamera | QVideoSource
    Description: TypeAlias = list[dict[str, str]]
    Change: TypeAlias = tuple[Parameter, str, QCamera.PropertyValue]
    Changes: TypeAlias = list[Change]

    @staticmethod
    def _getParameters(parameter: Parameter) -> None:
        '''Recursively find setters for named Parameters'''
        parameters = dict()
        if parameter.hasChildren():
            for p in parameter.children():
                parameters.update(QCameraTree._getParameters(p))
        else:
            name = parameter.name()  # .lower()
            parameters.update({name: parameter})
        return parameters

    @staticmethod
    def _defaultDescription(camera: QCamera) -> list:
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
                 description: Description | None,
                 *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if not source.isOpen():
            logger.error('Video source is not open')
            return
        if isinstance(source, QCamera):
            self.source = QVideoSource(source)
        else:
            self.source = source
        self._createTree(description)
        self._connectSignals()
        self._setupUi()

    def __del__(self) -> None:
        logger.debug('__del__ called')
        try:
            self.stop()
        except Exception as ex:
            logger.debug(f'__del__: {ex}')

    def _setupUi(self) -> None:
        self.setMinimumWidth(250)
        self.header().setSectionResizeMode(0, QHeaderView.Fixed)
        self.setColumnWidth(0, 150)

    def _createTree(self, description: Description | None) -> None:
        if description is None:
            description = self._defaultDescription(self.camera)
        self._tree = Parameter.create(name=self.camera.name,
                                      type='group',
                                      children=description)
        self.setParameters(self._tree, showTop=False)
        self._parameters = self._getParameters(self._tree)
        '''
        for name, parameter in self._parameters.items():
            print(name)
            parameter.setValue(self.camera.get(name))
        '''

    def _connectSignals(self) -> None:
        self._tree.sigTreeStateChanged.connect(self._sync)

    @pyqtSlot(object, object)
    def _sync(self, tree: ParameterTree, changes: Changes) -> None:
        for param, change, value in changes:
            if (change == 'value'):
                key = param.name()  # .lower()
                logger.debug(f'Syncing {key}: {change}: {value}')
                self.camera.set(key, value)

    @pyqtSlot(str, object)
    def set(self, key: str, value: QCamera.PropertyValue) -> None:
        if key in self._parameters:
            logger.debug(f'set {key}: {value}')
            self._parameters[key].setValue(value)
        else:
            logger.warning(f'Unsupported property: {key}')

    def get(self, key) -> QCamera.PropertyValue | None:
        if key in self._parameters:
            return self._parameters[key].getValue()
        else:
            logger.warning(f'Unsupported property: {key}')
        return None

    @pyqtProperty(QVideoSource)
    def source(self) -> QVideoSource:
        return self._source

    @source.setter
    def source(self, source: QVideoSource) -> None:
        self._source = source

    @pyqtProperty(QCamera)
    def camera(self) -> QCamera:
        return self.source.source

    @pyqtSlot()
    def start(self):
        self.source.start()
        return self

    @pyqtSlot()
    def stop(self) -> None:
        self.source.stop()
        self.source.quit()
        self.source.wait()

    @pyqtSlot()
    def close(self) -> None:
        self.stop()

    @classmethod
    def example(cls: 'QCameraTree') -> None:
        from PyQt5.QtWidgets import QApplication
        import sys

        app = QApplication(sys.argv)
        tree = cls().start()
        tree.show()
        sys.exit(app.exec())
