'''Auto-building pyqtgraph parameter tree for QCamera property inspection.'''
import contextlib
import logging
import math
import time
from typing import Any, cast

from qtpy import QtCore, QtGui, QtWidgets
from pyqtgraph.parametertree import Parameter, ParameterTree

from QVideo.lib import QCamera, QVideoSource
from QVideo.lib import _sliderspin  # noqa: F401  registers 'sliderspin'
from QVideo.lib._qapp import stopAtQuit
from QVideo.lib._writequeue import Batch, WriteQueue


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

    Requests to change camera properties are queued in a worker thread
    to avoid blocking the GUI and are batched to ensure that only the
    most recent value for each property is written to the camera. This
    means that values displayed on the GUI may not be written to the
    camera until the end of a frame interval, and some requests in a
    stream of requests may be dropped silently. Calling :meth:`flush`
    waits for the camera to have the latest values, which can be useful
    in scripts or tests.

    Parameters
    ----------
    source : QCamera or QVideoSource
        The video source to control.  Must already be open.
    description : list[dict] or None
        Parameter-tree description of the camera properties to expose.
        If ``None`` a default description is generated from
        :attr:`~QVideo.lib.QCamera.QCamera.settings`.
    threaded : bool
        Write the camera in a worker thread (the default).  ``False`` writes
        it in the interface thread, inside the change, as before: the
        interface waits for the camera, and a write has taken effect when the
        change returns.
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
        string with limits is a list, and a number that has a range is a slider
        with a spin box.
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
            elif (type(value) in (int, float)
                  and spec.minimum is not None and spec.maximum is not None
                  and spec.minimum < spec.maximum):
                # A number with a range: a slider and a spin box, whether or
                # not it can be written now (a camera unlocks the exposure
                # time when the exposure is manual), so that it has one when
                # it can.  The control is locked while it cannot.
                entry.update(type='sliderspin', int=type(value) is int,
                             limits=(spec.minimum, spec.maximum))
                if type(value) is int and spec.step is not None:
                    entry['step'] = spec.step
            entries.append(entry)
        return entries

    #: Emitted, from the worker thread, with ``(values, edits)``: what the
    #: camera answered after a batch of writes, and the number of the last
    #: edit of each property that the batch carried.
    _written = QtCore.Signal(object)

    def __init__(self,
                 source: Source,
                 description: Description | None = None,
                 *args,
                 threaded: bool = True,
                 **kwargs) -> None:
        if not source.isOpen():     # before there is a widget to discard
            raise RuntimeError('Video source is not open')
        kwargs.setdefault('showHeader', False)
        super().__init__(*args, **kwargs)
        if isinstance(source, QCamera):
            self._source = QVideoSource(source)
        else:
            self._source = source
        self._ignoreSync = False
        # The edits of each property: counted when the user makes one, and
        # the count that the camera has written.  A property whose count is
        # ahead has a change that the camera has not seen, and what the
        # camera answers about it is out of date.
        self._edits: dict[str, int] = {}
        self._applied: dict[str, int] = {}
        self._queue: WriteQueue | None = None
        self._emitted = self._shown = 0
        if threaded:
            self._queue = WriteQueue(self._work, f'{type(self).__name__} '
                                     'writer')
            self._written.connect(self._showWritten)
        self._createTree(description)
        self._connectSignals()
        self._setupUi()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        '''Stop the writer and the video source when the widget is closed.'''
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
        kind = param.opts.get('type')
        if kind != 'float' and not (kind == 'sliderspin'
                                    and not param.opts.get('int')):
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
                        and not self._outstanding(key)
                        and self._differs(self._parameters[key].value(),
                                          value)):
                    self.set(key, value)
        self._showAccess()

    def _outstanding(self, key: str) -> bool:
        '''Return whether the user has changed *key* since the camera last
        wrote it: what the camera says about it is out of date.'''
        return self._edits.get(key, 0) > self._applied.get(key, 0)

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
        '''Send changes made in the tree to the camera.

        Queue requests from the user to change camera settings.
        Changing one setting may cause the camera to change
        additional settings. The tree therefore refreshes displayed
        settings from the actual state of the camera after requesting
        a change. Writing and readback are performed by a worker
        thread unless the tree is not ``threaded``;
        see :meth:`_work` and :meth:`_show`.
        '''
        if self._ignoreSync:
            return
        batch: Batch = {}
        for param, change, value in changes:
            if change == 'value':
                key = param.name()
                logger.debug(f'Syncing {key}: {change}: {value}')
                self._updateStep(param)
                self._edits[key] = self._edits.get(key, 0) + 1
                batch.pop(key, None)
                batch[key] = (value, self._edits[key])
        if not batch:
            return
        if self._queue is None:                 # not threaded: here and now
            self._show(*self._write(batch))
            return
        for key, (value, edits) in batch.items():
            self._queue.put(key, value, edits)

    def _work(self, batch: Batch) -> None:
        '''In the worker thread: write *batch* and hand the answer over.'''
        answer = self._write(batch)
        self._emitted += 1
        try:
            self._written.emit(answer)
        except RuntimeError:                    # the tree was deleted
            logger.debug('the tree is gone: the answer is dropped')

    def _write(self, batch: Batch) -> tuple[dict, dict[str, int]]:
        '''Write *batch* to the camera and read back.

        Returns the values that the camera has, and the number of the last
        edit that was written for each property.  A write that the camera
        refuses is logged, and the readback then shows the user what the
        camera has.
        '''
        edits: dict[str, int] = {}
        for key, (value, count) in batch.items():
            try:
                self.camera.set(key, self._toCamera(key, value))
            except Exception:
                logger.exception(f'the camera refused {key} = {value!r}')
            edits[key] = count
        try:
            values = self._readback()
        except Exception:
            logger.exception('the camera could not be read back')
            values = {}
        return values, edits

    @QtCore.Slot(object)
    def _showWritten(self, answer: tuple[dict, dict[str, int]]) -> None:
        '''In the interface thread: show what the worker brought.'''
        self._shown += 1
        self._show(*answer)

    def _show(self, values: dict, edits: dict[str, int]) -> None:
        '''Show *values*, the camera's answer after the writes that carried
        *edits*, except where the user has changed the property since.

        The others who show the camera (a web page) are told what it has.
        '''
        for key, count in edits.items():
            self._applied[key] = max(count, self._applied.get(key, 0))
        current = {key: value for key, value in values.items()
                   if not self._outstanding(key)}
        with self._syncIgnored():
            for key, value in current.items():
                if key in self._parameters:
                    self.set(key, self._fromCamera(key, value))
        self._showAccess()
        self._announce(current)

    # The places where a tree for a camera that needs more may differ.

    def _toCamera(self, key: str, value: Any) -> Any:
        '''Return the value of control *key* as the camera takes it.'''
        return value

    def _fromCamera(self, key: str, value: Any) -> Any:
        '''Return the value of property *key* as the control shows it.'''
        return value

    def _readback(self) -> dict:
        '''Read, in one request, what the controls show (called in the
        worker thread).'''
        return self.camera.snapshot(self._parameters)

    def _announce(self, values: dict) -> None:
        '''Tell the others who show the camera what it has.'''
        self.camera.propertiesChanged.emit(values)

    def flush(self, timeout: float = 10.) -> bool:
        '''Wait until the camera has the changes made in the tree and the
        tree has shown its answer.

        Call it from the interface thread, in a script or a test that needs
        a change to have taken effect.  It processes events while it waits.

        Parameters
        ----------
        timeout : float
            The longest to wait [s].

        Returns
        -------
        bool
            ``True`` if the writes are done and shown, ``False`` if the time
            ran out.  A tree that is not ``threaded`` is always done.
        '''
        if self._queue is None:
            return True
        end = time.monotonic() + timeout
        while True:
            QtCore.QCoreApplication.processEvents()
            if self._queue.idle() and self._shown == self._emitted:
                return True
            if time.monotonic() >= end:
                return False
            time.sleep(0.001)

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
        '''Stop the writer and join the video source thread.

        Writes that are waiting are dropped; the one in progress is
        finished first.
        '''
        if self._queue is not None:
            self._queue.close()
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
