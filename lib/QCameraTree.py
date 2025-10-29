from pyqtgraph.parametertree import (Parameter, ParameterTree)
from pyqtgraph.Qt.QtCore import (pyqtSlot, pyqtProperty)
from pyqtgraph.Qt.QtWidgets import QHeaderView
from QVideo.lib import (QCamera, QVideoSource)
from typing import TypeAlias
import logging


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class QCameraTree(ParameterTree):

    '''A parameter tree widget for controlling QCamera properties.

    Parameters
    ----------
    source : QCamera | QVideoSource
        The video source to control.
    description : list[dict[str, str]] | None
        Optional description of camera properties to display
        in the parameter tree. If None, a default description
        is generated from the camera settings.
    args : list
        Additional positional arguments to pass to the ParameterTree constructor.
    kwargs : dict
        Additional keyword arguments to pass to the ParameterTree constructor.
    Returns
    -------
    QCameraTree : ParameterTree
        The camera control tree widget.

    Properties
    ----------
    source : QVideoSource
        The video source object.
    camera : QCamera
        The camera object.

    Methods
    -------
    start() -> QCameraTree
        Start the video source.
    stop() -> None
        Stop the video source.
    close() -> None
        Close the video source.
    set(key: str, value: QCamera.PropertyValue) -> None
        Set a camera property value.
    get(key: str) -> QCamera.PropertyValue | None
        Get a camera property value.
    example() -> None
        Run an example of the QCameraTree widget.
    '''

    Source: TypeAlias = QCamera | QVideoSource
    Description: TypeAlias = list[dict[str, str]]
    Change: TypeAlias = tuple[Parameter, str, QCamera.PropertyValue]
    Changes: TypeAlias = list[Change]

    @staticmethod
    def _getParameters(parameter: Parameter) -> dict[str, object]:
        '''Recursively find setters for named Parameters'''
        parameters = dict()
        if parameter.hasChildren():
            for p in parameter.children():
                parameters.update(QCameraTree._getParameters(p))
        else:
            name = parameter.name()
            parameters.update({name: parameter})
        return parameters

    @staticmethod
    def _defaultDescription(camera: QCamera) -> list:
        settings = camera.settings().items()
        entries = [{'name': key,
                    'type': value.__class__.__name__,
                    'value': value}
                   for key, value in settings if value is not None]
        return entries

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

    def _createTree(self, description: Description | None) -> None:
        if description is None:
            description = self._defaultDescription(self.camera)
        self._tree = Parameter.create(name=self.camera.name,
                                      type='group',
                                      children=description)
        self.setParameters(self._tree)
        self._parameters = self._getParameters(self._tree)

    def _connectSignals(self) -> None:
        self._tree.sigTreeStateChanged.connect(self._sync)
        self._ignoresync = False

    def _setupUi(self) -> None:
        '''
        FIXME: Resize to fit contents?
        '''
        self.setMinimumWidth(250)
        self.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.setColumnWidth(0, 200)

    @pyqtSlot(object, object)
    def _sync(self, tree: ParameterTree, changes: Changes) -> None:
        if self._ignoresync:
            return
        for param, change, value in changes:
            if (change == 'value'):
                key = param.name()  # .lower()
                logger.debug(f'Syncing {key}: {change}: {value}')
                self.camera.set(key, value)
        self._ignoresync = True
        for key, value in self.camera.settings().items():
            self.set(key, value)
        self._ignoresync = False

    @pyqtSlot(str, object)
    def set(self, key: str, value: QCamera.PropertyValue) -> None:
        if key in self._parameters:
            logger.debug(f'set {key}: {value}')
            self._parameters[key].setValue(value)
        else:
            logger.warning(f'Unsupported property: {key}')

    def get(self, key: str) -> QCamera.PropertyValue | None:
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
        from pyqtgraph.Qt.QtWidgets import QApplication
        import sys

        app = QApplication(sys.argv)
        tree = cls().start()
        tree.show()
        sys.exit(app.exec())
