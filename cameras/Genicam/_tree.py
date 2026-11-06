'''Camera property tree for GenICam cameras.'''
from typing import Any, ClassVar
import math
from collections.abc import Sequence
from qtpy import QtCore
from QVideo.lib import QCameraTree
from QVideo.cameras.Genicam import QGenicamCamera
from genicam.genapi import EAccessMode, EVisibility
import logging


logger = logging.getLogger(__name__)

_MICROSECOND_UNITS = frozenset({'us', 'µs', 'μs'})

__all__ = ['QGenicamTree']


class QGenicamTree(QCameraTree):

    '''Camera property tree for
    :class:`~QVideo.cameras.Genicam.QGenicamCamera`.

    Builds a :class:`~QVideo.lib.QCameraTree.QCameraTree` from the camera's
    GenICam node map and exposes visibility and per-feature enable/disable
    controls.

    A timer polls the camera periodically so that autonomous camera-side
    changes (e.g. ``Gain`` being adjusted by auto-exposure, ``GainAuto``
    reverting from ``"Once"`` to ``"Off"``) are reflected in the UI.
    ``PyNodeCallback`` is not used because it only fires when the **host**
    writes a node, not when the camera changes a value autonomously.

    Parameters
    ----------
    camera : QGenicamCamera or None
        Camera instance to use.  If ``None``, the tree opens a camera of
        its :attr:`_cameraClass` from ``cameraID``.
    cameraID : int
        Index of the camera to open.  Used only when *camera* is
        ``None``.  Default: ``0``.
    visibility : EVisibility
        Maximum GenICam visibility level to display.
        Default: ``EVisibility.Guru``.
    controls : list of str or None
        If given, only nodes whose names appear in this list are shown;
        all others are hidden.  Default: :attr:`_DEFAULT_CONTROLS`, which
        is ``None`` (show all) unless a subclass sets it.
    *args :
        Forwarded to :class:`~QVideo.lib.QCameraTree.QCameraTree`.
    **kwargs :
        Forwarded to :class:`~QVideo.lib.QCameraTree.QCameraTree`.
    '''

    #: The controls that most cameras offer, by their SFNC names.
    STANDARD_CONTROLS = (
        'ReverseX',
        'ReverseY',
        'AcquisitionFrameRate',
        'AcquisitionResultingFrameRate',
        'ExposureTime',
        'ExposureAuto',
        'Gain',
        'GainAuto',
        'GammaEnable',
        'Gamma',
        'BlackLevel',
        'Width',
        'Height',
        'OffsetX',
        'OffsetY',
    )

    #: The camera class of a tree for one vendor; its subclass sets it.
    _cameraClass: type[QGenicamCamera] | None = None

    #: The controls to show when the caller names none, or ``None`` for
    #: all of them.
    _DEFAULT_CONTROLS: tuple[str, ...] | None = None

    #: Settings that the tree applies to the camera, those that the camera
    #: has, so that the controls start in a known state.  Gamma is 1 and
    #: off, as scientific applications expect; a vendor tree that sets its
    #: own defaults starts from these.
    _DEFAULT_SETTINGS: ClassVar[dict[str, object]] = dict(
        Gamma=1.0,
        GammaEnable=False,
    )

    #: Parameters that one poll of the camera reads.
    _pollChunk = 32

    def __init__(self, *args,
                 camera: QGenicamCamera | None = None,
                 cameraID: int = 0,
                 visibility: EVisibility = EVisibility.Guru,
                 controls: Sequence[str] | None = None,
                 **kwargs) -> None:
        if camera is None:
            camera = self._cameraClass(cameraID=cameraID)
        settings = {key: value
                    for key, value in self._DEFAULT_SETTINGS.items()
                    if key in camera.properties}
        if settings:
            camera.settings = settings
        controls = controls or self._DEFAULT_CONTROLS
        self._pollCursor = 0
        self._scaleFactors: dict[str, float] = {}
        self._decParams: set[str] = set()
        self._visibilities: dict[str, int] = {}
        description = self.description(camera)
        super().__init__(camera, description, *args, **kwargs)
        self._visibility = visibility
        self.controls = controls
        self.visibility = visibility
        self._updateEnabled()
        self._startTimer()

    def _startTimer(self) -> None:
        '''Start the timer to poll camera-side changes.'''
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self._pollCamera)
        self._timer.start()
        instance = QtCore.QCoreApplication.instance()
        quitting = instance.aboutToQuit
        quitting.connect(self._timer.stop)

    def closeEvent(self, event) -> None:
        self._timer.stop()
        super().closeEvent(event)

    def description(self,
                    camera: QGenicamCamera) -> list[dict]:
        '''Return a list of dicts describing the node map.

        The camera describes its nodes as plain data
        (:meth:`~QVideo.cameras.Genicam.QGenicamCamera.nodeTree`), so the
        same tree works for a camera in a process of its own.
        '''
        root = camera.nodeTree()
        if not root:
            return []
        return self.describe(root).get('children', [])

    def describe(self, node: dict[str, Any]) -> dict[str, Any]:
        '''Return the description of *node* for the parameter tree.

        Records the names and visibilities of the nodes, and the scale
        and step of the floats.
        '''
        this = dict(node)
        self._visibilities[node['name']] = node['visibility']
        if 'children' in node:
            this['children'] = [self.describe(c) for c in node['children']]
        elif node.get('type') == 'float':
            self._describeFloat(this)
        return this

    def _describeFloat(self, this: dict[str, Any]) -> None:
        '''Apply units, scale and step to the float description *this*.'''
        name = this['name']
        unit = this.pop('unit', None)
        step = this.pop('step', None)
        if unit in _MICROSECOND_UNITS:
            scale = 1e-6
            self._scaleFactors[name] = scale
            this['siPrefix'] = True
            unit = 's'
        else:
            scale = 1.0
        value = this['value'] * scale
        this['value'] = this['default'] = value
        lo = this['min'] = this['min'] * scale
        hi = this['max'] = this['max'] * scale
        this['units'] = unit
        if step is not None:
            this['step'] = step * scale
        if lo > 0 and hi / lo > 100:
            self._decParams.add(name)
            if value > 0:
                this['step'] = 10 ** (math.floor(math.log10(value)) - 1)

    def _connectSignals(self) -> None:
        super()._connectSignals()
        for item in self.listAllItems():
            p = item.param
            p.sigValueChanged.connect(self._handleItemChanges)

    @QtCore.Slot(object, object)
    def _sync(self, root, changes) -> None:
        if self._ignoreSync:
            return
        for param, change, value in changes:
            if change == 'value':
                key = param.name()
                scale = self._scaleFactors.get(key)
                sent = value if scale is None else value / scale
                self.camera.set(key, sent)
        with self._syncIgnored():
            for key, value in self.camera.settings.items():
                scale = self._scaleFactors.get(key)
                self.set(key, value if scale is None else value * scale)

    @property
    def controls(self) -> Sequence[str] | None:
        '''Names of the nodes to show, or ``None`` to show all of them.'''
        return self._controls

    @controls.setter
    def controls(self, controls: Sequence[str] | None) -> None:
        self._controls = controls
        for item in self.listAllItems()[1:]:
            p = item.param
            name = p.opts['name']
            visible = controls is None or name in controls
            p.opts['visibility'] = (EVisibility(self._visibilities[name])
                                    if visible and name in self._visibilities
                                    else EVisibility.Invisible)
        self._updateVisible()

    @property
    def visibility(self) -> EVisibility:
        '''The highest GenICam visibility level that the tree shows.'''
        return self._visibility

    @visibility.setter
    def visibility(self, visibility: EVisibility) -> None:
        self._visibility = visibility
        self._updateVisible()

    def _handleItemChanges(self) -> None:
        if self._ignoreSync:
            return
        logger.debug('Handling item changes')
        self._updateVisible()
        params, states = self._snapshot()
        self._updateEnabled(params, states)
        self._updateLimits(params, states)
        self._updateValues(params, states)

    def _updateVisible(self) -> None:
        '''Show the parameters that should be visible.

        Showing or hiding a row changes no value, but every change that
        pyqtgraph reports would make :meth:`_sync` read all of the
        camera's settings again, once for each row.
        '''
        with self._syncIgnored():
            for item in self.listAllItems()[1:]:
                p = item.param
                p.setOpts(visible=self.visible(p))
        self.camera.watch([name for _, name in self._visibleParams()])

    def visible(self, param) -> bool:
        '''Return whether *param* is shown: it is not an action, its
        visibility does not exceed :attr:`visibility`, and a group has a
        child that is shown.'''
        ptype = param.opts['type']
        if ptype in ('action', None):
            return False
        if ptype == 'group':
            return any(self.visible(c) for c in param.children())
        get = param.opts.get
        visibility = get('visibility', EVisibility.Invisible)
        return visibility <= self.visibility

    def _visibleParams(self) -> list[tuple[Any, str]]:
        '''Return the visible parameters that the camera has, with names.'''
        pairs = ((item.param, item.param.opts.get('name'))
                 for item in self.listAllItems()[1:])
        return [(p, name) for p, name in pairs
                if p.opts.get('visible', False) and name in self._visibilities]

    def _snapshot(self, params: list | None = None,
                  cached: bool = False) -> tuple[list, dict]:
        '''Read the nodes of *params* together, under one lock.

        The camera thread holds the lock while it waits for a frame, so
        the interface asks for the nodes that it needs in one request.
        '''
        if params is None:
            params = self._visibleParams()
        states = self.camera.states([name for _, name in params],
                                    cached=cached)
        return [(p, name) for p, name in params if name in states], states

    def _updateEnabled(self, params: list | None = None,
                       states: dict | None = None) -> None:
        if states is None:
            params, states = self._snapshot(params)
        for p, name in params:
            p.setOpts(enabled=states[name]['writable'])

    def _updateLimits(self, params: list | None = None,
                      states: dict | None = None) -> None:
        '''Refresh Parameter constraints from the live GenICam node values.

        Called after every property change so that dependent nodes (e.g.
        ``OffsetX`` range after a ``Width`` change) reflect the current
        hardware state in the UI.  Only visible leaf parameters are updated.
        '''
        if states is None:
            params, states = self._snapshot(params)
        for p, name in params:
            state = states[name]
            kind, inc = state['kind'], state.get('inc')
            if kind == 'int':
                p.setOpts(limits=(state['min'], state['max']), step=inc)
            elif kind == 'float':
                scale = self._scaleFactors.get(name, 1.0)
                opts = {'limits': (state['min'] * scale,
                                   state['max'] * scale)}
                if name in self._decParams:
                    value = p.value()
                    if value > 0:
                        step = 10 ** (math.floor(math.log10(value)) - 1)
                        if inc is not None:
                            step = max(step, inc * scale)
                        opts['step'] = step
                elif inc is not None:
                    opts['step'] = inc * scale
                p.setOpts(**opts)
            elif kind == 'enum':
                p.setOpts(limits=state['entries'])

    def _scaledValue(self, name: str, state: dict) -> object:
        '''Return the value in a node snapshot, applying any scale factor.'''
        value = state.get('value')
        if value is not None and name in self._scaleFactors:
            value *= self._scaleFactors[name]
        return value

    def _updateValues(self, params: list | None = None,
                      states: dict | None = None) -> None:
        '''Refresh read-only Parameter values from the live GenICam node map.

        Called after every property change so that derived read-only nodes
        (e.g. ``AcquisitionResultingFrameRate``) reflect the current hardware
        state in the UI.  Only visible read-only leaf parameters are updated.
        Signals are blocked during the update to prevent re-entrant calls.
        '''
        if states is None:
            params, states = self._snapshot(params)
        for p, name in params:
            state = states[name]
            if state['access'] != EAccessMode.RO:
                continue
            if state['kind'] == 'register':
                continue
            value = self._scaledValue(name, state)
            if value is None:
                continue
            p.blockSignals(True)
            try:
                p.setValue(value)
            finally:
                p.blockSignals(False)

    def _pollCamera(self) -> None:
        '''Refresh the next few Parameters from the camera.

        Called by the poll timer to pick up autonomous camera-side changes
        that do not generate host-side notifications — e.g. ``Gain`` being
        adjusted during auto-exposure, or ``GainAuto`` reverting from
        ``"Once"`` to ``"Off"`` after the sweep completes.

        Each call reads :attr:`_pollChunk` parameters in a single request
        and the next call the following ones, so that no call holds the
        camera from its frames for long; a full cycle takes
        ``len(params) / _pollChunk`` calls.  Limits, values and enabled
        states of the chunk are refreshed from the same snapshot.

        Returns immediately if the camera is no longer open (e.g. during
        application shutdown) to prevent accessing freed C++ genapi objects.

        Signals are not blocked so that the visual widgets update and
        :meth:`_handleItemChanges` fires when a value changes.
        :meth:`_syncIgnored` is in force for the duration so that the resulting
        ``sigTreeStateChanged`` emissions do not send values back to the
        camera.  Access-mode changes (e.g. ``ExposureTime`` becoming
        writable again after the sweep) are reflected even when the
        controlling node value has not changed.
        '''
        if not self.camera.isOpen():
            return
        params = self._visibleParams()
        if self._pollCursor >= len(params):
            self._pollCursor = 0
        chunk = params[self._pollCursor:self._pollCursor + self._pollChunk]
        self._pollCursor += self._pollChunk
        params, states = self._snapshot(chunk, cached=True)
        with self._syncIgnored():
            self._updateLimits(params, states)
            for p, name in params:
                state = states[name]
                if state['access'] not in (EAccessMode.RO, EAccessMode.RW):
                    continue
                if state['kind'] == 'register':
                    continue  # raw memory: read once, when the tree is built
                value = self._scaledValue(name, state)
                if value is None:
                    continue
                p.setValue(value)
            self._updateEnabled(params, states)


if __name__ == '__main__':  # pragma: no cover
    QGenicamTree.example()
