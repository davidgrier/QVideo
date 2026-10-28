'''Camera property tree for GenICam cameras.'''
from typing import Any
import math
from qtpy import QtCore
from QVideo.lib import QCameraTree
from QVideo.cameras.Genicam import QGenicamCamera
from genicam.genapi import (IValue, EAccessMode, EVisibility,
                            ICategory, ICommand, IEnumeration,
                            IBoolean, IInteger, IFloat, IString,
                            IRegister)
from QVideo.cameras.Genicam._camera import registerText
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
    camera : QGenicamCamera
        Camera instance to use.
    visibility : EVisibility
        Maximum GenICam visibility level to display.
        Default: ``EVisibility.Guru``.
    controls : list of str or None
        If given, only nodes whose names appear in this list are shown;
        all others are hidden.  Default: ``None`` (show all).
    *args :
        Forwarded to :class:`~QVideo.lib.QCameraTree.QCameraTree`.
    **kwargs :
        Forwarded to :class:`~QVideo.lib.QCameraTree.QCameraTree`.
    '''

    #: Parameters that one poll of the camera reads.
    _pollChunk = 32

    def __init__(self, *args,
                 camera: QGenicamCamera,
                 visibility: EVisibility = EVisibility.Guru,
                 controls: list[str] | None = None,
                 **kwargs) -> None:
        self._pollCursor = 0
        self._scaleFactors: dict[str, float] = {}
        self._decParams: set[str] = set()
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
        '''Return a list of dicts describing the node map'''
        root = camera.node('Root')
        if root is None:
            return []
        description = self.describe(root)
        return description.get('children', [])

    def describe(self, feature: IValue) -> dict[str, Any]:
        '''Return a dictionary describing a feature'''
        this = dict(name=feature.node.name,
                    title=feature.node.display_name,
                    visibility=feature.node.visibility)
        mode = feature.node.get_access_mode()
        if mode == EAccessMode.NI:
            return this
        if isinstance(feature, ICategory):
            this['type'] = 'group'
            this['children'] = [self.describe(f)
                                for f in feature.features]
            return this
        if isinstance(feature, ICommand):
            this['type'] = 'action'
            return this
        if mode not in (EAccessMode.RW, EAccessMode.RO):
            return this
        if isinstance(feature, IEnumeration):
            this['type'] = 'list'
            this['value'] = this['default'] = feature.to_string()
            this['limits'] = [v.symbolic for v in feature.entries]
        elif isinstance(feature, IBoolean):
            this['type'] = 'bool'
            this['value'] = this['default'] = feature.value
        elif isinstance(feature, IInteger):
            this['type'] = 'int'
            this['value'] = this['default'] = feature.value
            this['min'] = feature.min
            this['max'] = feature.max
            this['step'] = feature.inc
        elif isinstance(feature, IFloat):
            this['type'] = 'float'
            self._describeFloat(feature, this)
        elif isinstance(feature, IString):
            this['type'] = 'str'
            this['value'] = this['default'] = feature.value
        elif isinstance(feature, IRegister):
            # A register is a raw block of the camera's memory: show its
            # bytes as read-only text.
            this['type'] = 'str'
            this['value'] = this['default'] = registerText(feature)
            this['readonly'] = True
        else:
            logger.debug(
                f'Unsupported node type: {feature.node.name}: {type(feature)}')
        return this

    def _describeFloat(self, feature: IFloat, this: dict[str, Any]) -> None:
        '''Add the value, limits, units and step of a float *feature*.'''
        unit = feature.unit
        if unit in _MICROSECOND_UNITS:
            scale = 1e-6
            self._scaleFactors[feature.node.name] = scale
            this['siPrefix'] = True
            unit = 's'
        else:
            scale = 1.0
        this['value'] = this['default'] = feature.value * scale
        lo = feature.min * scale
        hi = feature.max * scale
        this['min'] = lo
        this['max'] = hi
        this['units'] = unit
        if feature.has_inc():
            this['step'] = feature.inc * scale
        if lo > 0 and hi / lo > 100:
            self._decParams.add(feature.node.name)
            v = feature.value * scale
            if v > 0:
                this['step'] = 10 ** (math.floor(math.log10(v)) - 1)

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
                if key in self._scaleFactors:
                    value = value / self._scaleFactors[key]  # type: ignore
                self.camera.set(key, value)
        self._ignoreSync = True
        for key, value in self.camera.settings.items():
            if key in self._scaleFactors:
                value = value * self._scaleFactors[key]  # type: ignore
            self.set(key, value)
        self._ignoreSync = False

    @property
    def controls(self) -> list[str] | None:
        return self._controls

    @controls.setter
    def controls(self, controls: list[str] | None) -> None:
        self._controls = controls
        for item in self.listAllItems()[1:]:
            p = item.param
            name = p.opts['name']
            node = self.camera.node(name)
            visible = controls is None or name in controls
            p.opts['visibility'] = (node.node.visibility
                                    if node is not None and visible
                                    else EVisibility.Invisible)
        self._updateVisible()

    @property
    def visibility(self) -> EVisibility:
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
        ignoring, self._ignoreSync = self._ignoreSync, True
        try:
            for item in self.listAllItems()[1:]:
                p = item.param
                p.setOpts(visible=self.visible(p))
        finally:
            self._ignoreSync = ignoring

    def visible(self, param) -> bool:
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
                if p.opts.get('visible', False) and self.camera.hasNode(name)]

    def _snapshot(self, params: list | None = None) -> tuple[list, dict]:
        '''Read the nodes of *params* together, under one lock.

        The camera thread holds the lock while it waits for a frame, so
        the interface asks for the nodes that it needs in one request.
        '''
        if params is None:
            params = self._visibleParams()
        return params, self.camera.states([name for _, name in params])

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
        :attr:`_ignoreSync` is set for the duration so that the resulting
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
        params, states = self._snapshot(chunk)
        self._ignoreSync = True
        try:
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
        finally:
            self._ignoreSync = False


if __name__ == '__main__':  # pragma: no cover
    QGenicamTree.example()
