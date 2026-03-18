from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.parametertree import Parameter, ParameterTree
from QVideo.lib import QCamera, QVideoSource
import logging


__all__ = ['QCameraTree']


logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


Source = QCamera | QVideoSource
Description = list[dict[str, str]]
Change = tuple[Parameter, str, QCamera.PropertyValue]
Changes = list[Change]


class QCameraTree(ParameterTree):

    '''A parameter tree widget for controlling :class:`~QVideo.lib.QCamera.QCamera` properties.

    Wraps a :class:`~QVideo.lib.QVideoSource.QVideoSource` (or a bare
    :class:`~QVideo.lib.QCamera.QCamera`) and presents its settings as
    an editable :class:`~pyqtgraph.parametertree.ParameterTree`.
    Changes made in the tree are pushed to the camera; camera-side
    changes are reflected back into the tree.

    Parameters
    ----------
    source : QCamera or QVideoSource
        The video source to control.  Must already be open.
    description : list[dict] or None
        Parameter-tree description of the camera properties to expose.
        If ``None`` a default description is generated from
        :attr:`~QVideo.lib.QCamera.QCamera.settings`.
    *args :
        Additional positional arguments forwarded to
        :class:`~pyqtgraph.parametertree.ParameterTree`.
    **kwargs :
        Additional keyword arguments forwarded to
        :class:`~pyqtgraph.parametertree.ParameterTree`.

    Raises
    ------
    RuntimeError
        If *source* is not open when the tree is created.
    '''

    @classmethod
    def _getParameters(cls, parameter: Parameter) -> dict[str, object]:
        '''Recursively collect leaf :class:`~pyqtgraph.parametertree.Parameter` nodes.'''
        parameters = dict()
        for child in parameter.children():
            if child.hasChildren():
                parameters.update(cls._getParameters(child))
            else:
                parameters.update({child.name(): child})
        return parameters

    @staticmethod
    def _defaultDescription(camera: QCamera) -> Description:
        entries = []
        for name, spec in camera._properties.items():
            value = spec['getter']()
            if value is None:
                continue
            entry = {'name': name,
                     'type': type(value).__name__,
                     'value': value,
                     'default': value}
            if spec['setter'] is None:
                entry['enabled'] = False
            entries.append(entry)
        return entries

    def __init__(self,
                 source: Source,
                 description: Description | None = None,
                 *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if not source.isOpen():
            raise RuntimeError('Video source is not open')
        if isinstance(source, QCamera):
            self._source = QVideoSource(source)
        else:
            self._source = source
        self._ignoreSync = False
        self._createTree(description)
        self._connectSignals()
        self._setupUi()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        '''Stop the video source when the widget is closed.'''
        self.stop()
        super().closeEvent(event)

    def _createTree(self, description: Description | None) -> None:
        if description is None:
            description = self._defaultDescription(self.camera)
        logger.debug(description)
        self._tree = Parameter.create(name=self.camera.name,
                                      type='group',
                                      children=description)
        self.setParameters(self._tree)
        self._parameters = self._getParameters(self._tree)

    def _connectSignals(self) -> None:
        self._tree.sigTreeStateChanged.connect(self._sync)
        QtCore.QCoreApplication.instance().aboutToQuit.connect(self.stop)

    def _setupUi(self) -> None:
        header = self.header()
        self.setTextElideMode(QtCore.Qt.TextElideMode.ElideRight)
        policy = header.ResizeMode.Interactive
        header.setSectionResizeMode(policy)
        header.setStretchLastSection(False)
        for n in range(self.columnCount()):
            hint = self.sizeHintForColumn(n)
            header.resizeSection(n, hint + 20)
        self.adjustSize()
        self.setMinimumWidth(self.width())

    @QtCore.pyqtSlot(object, object)
    def _sync(self, root: Parameter, changes: Changes) -> None:
        if self._ignoreSync:
            return
        for param, change, value in changes:
            if (change == 'value'):
                key = param.name()
                logger.debug(f'Syncing {key}: {change}: {value}')
                self.camera.set(key, value)
        self._ignoreSync = True
        for key, value in self.camera.settings.items():
            self.set(key, value)
        self._ignoreSync = False

    @QtCore.pyqtSlot(str, object)
    def set(self, key: str, value: QCamera.PropertyValue) -> None:
        '''Set a camera property and update the tree.

        Parameters
        ----------
        key : str
            Property name.
        value : QCamera.PropertyValue
            New value.
        '''
        if key in self._parameters:
            logger.debug(f'set {key}: {value}')
            self._parameters[key].setValue(value)
        else:
            logger.warning(f'Unsupported property: {key}')

    def get(self, key: str) -> QCamera.PropertyValue | None:
        '''Get a camera property value from the tree.

        Parameters
        ----------
        key : str
            Property name.

        Returns
        -------
        QCamera.PropertyValue or None
            Current value, or ``None`` if *key* is not in the tree.
        '''
        if key in self._parameters:
            return self._parameters[key].value()
        logger.warning(f'Unsupported property: {key}')
        return None

    @QtCore.pyqtProperty(QVideoSource)
    def source(self) -> QVideoSource:
        '''The underlying :class:`~QVideo.lib.QVideoSource.QVideoSource`.'''
        return self._source

    @QtCore.pyqtProperty(QCamera)
    def camera(self) -> QCamera:
        '''The :class:`~QVideo.lib.QCamera.QCamera` driven by this tree.'''
        return self.source.source

    @QtCore.pyqtSlot()
    def start(self) -> 'QCameraTree':
        '''Start the video source.

        Returns
        -------
        QCameraTree
            ``self``, to allow chaining (e.g. ``tree = QCameraTree(...).start()``).
        '''
        self.source.start()
        return self

    @QtCore.pyqtSlot()
    def stop(self) -> None:
        '''Stop and join the video source thread.'''
        if self.source.isRunning():
            self.source.stop()
            self.source.quit()
            self.source.wait()

    @classmethod
    def example(cls: 'QCameraTree') -> None:  # pragma: no cover
        '''Demonstrate the widget with a default camera source.'''
        import pyqtgraph as pg

        app = pg.mkQApp(f'{cls.__name__} Example')
        tree = cls().start()
        tree.show()
        app.exec()
