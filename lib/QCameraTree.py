'''Auto-building pyqtgraph parameter tree for QCamera property inspection.'''
import contextlib
import logging
import math
from typing import cast

from qtpy import QtCore, QtGui, QtWidgets
from pyqtgraph.parametertree import Parameter, ParameterTree

from QVideo.lib import QCamera, QVideoSource
from QVideo.lib._qapp import stopAtQuit


__all__ = ['QCameraTree']

#: Height [pixels] that the tree asks for and is squeezed to at most.
_MIN_HEIGHT = 120


logger = logging.getLogger(__name__)


Source = QCamera | QVideoSource
Description = list[dict[str, object]]
Change = tuple[Parameter, str, QCamera.PropertyValue]
Changes = list[Change]


class QCameraTree(ParameterTree):

    '''A parameter tree widget for controlling
    :class:`~QVideo.lib.QCamera.QCamera` properties.

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
        :class:`~pyqtgraph.parametertree.ParameterTree`.  The tree has no
        header (the "Parameter" and "Value" labels say nothing that the
        rows do not); ``showHeader=True`` shows it.

    Raises
    ------
    RuntimeError
        If *source* is not open when the tree is created.
    '''

    @classmethod
    def _getParameters(cls, parameter: Parameter) -> dict[str, Parameter]:
        '''Recursively collect leaf
        :class:`~pyqtgraph.parametertree.Parameter` nodes.'''
        parameters = dict()
        for child in parameter.children():
            if child.hasChildren():
                parameters.update(cls._getParameters(child))
            else:
                parameters.update({child.name(): child})
        return parameters

    @staticmethod
    def _defaultDescription(camera: QCamera) -> Description:
        '''Describe the properties of *camera* that it can read now.

        A read-only property is disabled, a hidden one is not visible and a
        string with limits is a list.
        '''
        entries = []
        for name, spec in camera.properties.items():
            value = spec.getter()
            if value is None:
                continue
            entry = {'name': name,
                     'type': type(value).__name__,
                     'value': value,
                     'default': value}
            if spec.setter is None:
                entry['enabled'] = False
            if spec.hidden:
                entry['visible'] = False
            if spec.ptype is str and spec.limits:
                entry.update(type='list', limits=spec.limits)
            entries.append(entry)
        return entries

    def __init__(self,
                 source: Source,
                 description: Description | None = None,
                 *args, **kwargs) -> None:
        if not source.isOpen():     # before there is a widget to discard
            raise RuntimeError('Video source is not open')
        kwargs.setdefault('showHeader', False)
        super().__init__(*args, **kwargs)
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
        '''Make the parameter tree from *description*, or from the camera.'''
        if description is None:
            description = self._defaultDescription(self.camera)
        logger.debug(description)
        self._tree = Parameter.create(
            name=self.camera.modelName or self.camera.name,
            type='group',
            children=description)
        self.setParameters(self._tree)
        self._parameters = self._getParameters(self._tree)
        for param in self._parameters.values():
            self._updateStep(param)

    def _connectSignals(self) -> None:
        self._tree.sigTreeStateChanged.connect(self._sync)
        self._source.lost.connect(self._disable)
        self.camera.watch(self._parameters)
        self.camera.propertiesChanged.connect(self._showChanges)
        stopAtQuit(self.stop)

    def _setupUi(self) -> None:
        header = cast(QtWidgets.QHeaderView, self.header())
        self.setTextElideMode(QtCore.Qt.TextElideMode.ElideRight)
        self.setIndentation(10)
        count = self.columnCount()
        for n in range(count - 1):
            header.setSectionResizeMode(n, header.ResizeMode.Interactive)
            self.resizeColumnToContents(n)
        header.setSectionResizeMode(count - 1, header.ResizeMode.Stretch)
        self.adjustSize()
        self.setMinimumWidth(self.width())
        # The tree scrolls, so it asks for a few rows and takes the height
        # that its neighbors leave.
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred,
                           QtWidgets.QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(_MIN_HEIGHT)

    def sizeHint(self) -> QtCore.QSize:
        '''Ask for a few rows of height: the tree scrolls.'''
        return QtCore.QSize(super().sizeHint().width(), _MIN_HEIGHT)

    @staticmethod
    def _updateStep(param: Parameter) -> None:
        '''Scale a float SpinBox's step to ~10% of its current magnitude.

        pyqtgraph's ``dec=True`` mode jumps by a whole power of ten per
        scroll click, which is too coarse for camera properties (e.g.
        exposure time) that can span several orders of magnitude.
        Recomputing the step from the live value on every change keeps
        scrolling proportional at every magnitude instead.
        '''
        if param.opts.get('type') != 'float':
            return
        try:
            value = float(param.value())
        except (TypeError, ValueError):
            return
        if value == 0 or not math.isfinite(value):
            return
        step = 10 ** (math.floor(math.log10(abs(value))) - 1)
        param.setOpts(step=step)

    @contextlib.contextmanager
    def _syncIgnored(self):
        '''Ignore the changes that the tree reports while the block runs.

        Setting a parameter from the camera makes the tree report a
        change, which :meth:`_sync` would send back to the camera.  The
        blocks may nest, and the tree listens again when the outermost one
        ends, even if it raises.
        '''
        ignoring, self._ignoreSync = self._ignoreSync, True
        try:
            yield
        finally:
            self._ignoreSync = ignoring

    @QtCore.Slot(object)
    def _showChanges(self, values: dict) -> None:
        '''Show the values that the camera changed on its own.

        The camera reports them (see :meth:`QCamera.watch`): an automatic
        exposure settled, or a mode that turns itself off did.  They are
        not sent back.  The tree also shows which controls the camera lets
        us write now.
        '''
        with self._syncIgnored():
            for key, value in values.items():
                if (key in self._parameters
                        and self._differs(self._parameters[key].value(),
                                          value)):
                    self.set(key, value)
        self._showAccess()

    @staticmethod
    def _differs(shown: object, value: object) -> bool:
        '''Return whether the tree shows something other than *value*.'''
        if isinstance(shown, float) and isinstance(value, float):
            return not math.isclose(shown, value, rel_tol=1e-9, abs_tol=1e-12)
        return shown != value

    def _showAccess(self) -> None:
        '''Show which of the controls the camera lets us write.

        A camera changes what can be written as its settings change (the
        exposure time while the exposure is automatic), so a tree whose
        camera does that follows it.  The default does nothing.
        '''

    @QtCore.Slot(str)
    def _disable(self, reason: str) -> None:
        '''Disable the controls of a camera that is not there any more.

        The camera is closed and answers nothing, so a control that is
        still enabled can only be changed to no effect.
        '''
        self.setEnabled(False)
        self.setToolTip(f'The camera was lost: {reason}')

    @QtCore.Slot(object, object)
    def _sync(self, root: Parameter, changes: Changes) -> None:
        '''Send the changes made in the tree to the camera, then show it.

        The camera may change more than it was asked to (a longer exposure
        slows the frame rate), so the tree reads back the properties that
        it shows, and only those: a camera has many more properties than a
        tree has controls.  A property that cannot be read at the moment
        keeps its value in the tree.  They are read in one request
        (:meth:`QCamera.snapshot`), which waits for at most one frame: the
        capture thread holds the camera while it waits for one.
        '''
        if self._ignoreSync:
            return
        for param, change, value in changes:
            if change == 'value':
                key = param.name()
                logger.debug(f'Syncing {key}: {change}: {value}')
                self.camera.set(key, value)
                self._updateStep(param)
        values = self.camera.snapshot(self._parameters)
        with self._syncIgnored():
            for key, value in values.items():
                self.set(key, value)

    @QtCore.Slot(str, object)
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
            param = self._parameters[key]
            param.setValue(value)
            self._updateStep(param)
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

    @property
    def source(self) -> QVideoSource:
        '''The underlying :class:`~QVideo.lib.QVideoSource.QVideoSource`.'''
        return self._source

    @property
    def camera(self) -> QCamera:
        '''The :class:`~QVideo.lib.QCamera.QCamera` driven by this tree.'''
        return cast(QCamera, self.source.source)

    @QtCore.Slot()
    def start(self) -> 'QCameraTree':
        '''Start the video source.

        Returns
        -------
        QCameraTree
            ``self``, to allow chaining
            (e.g. ``tree = QCameraTree(...).start()``).
        '''
        self.source.start()
        return self

    @QtCore.Slot()
    def stop(self) -> None:
        '''Stop and join the video source thread.'''
        if self.source.isRunning():
            self.source.stop()

    @classmethod
    def example(cls: type['QCameraTree']) -> None:  # pragma: no cover
        '''Demonstrate the widget with a default camera source.'''
        import pyqtgraph as pg

        app = pg.mkQApp(f'{cls.__name__} Example')
        tree = cls().start()  # pyright: ignore[reportCallIssue]
        tree.show()
        app.exec()
