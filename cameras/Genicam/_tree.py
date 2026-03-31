from qtpy import QtCore
from QVideo.lib import QCameraTree
from QVideo.lib.QCameraTree import Source
from QVideo.cameras.Genicam import QGenicamCamera
from genicam.genapi import (IValue, EAccessMode, EVisibility,
                            ICategory, ICommand, IEnumeration,
                            IBoolean, IInteger, IFloat, IString)
import logging


logger = logging.getLogger(__name__)


__all__ = ['QGenicamTree']


class QGenicamTree(QCameraTree):

    '''Camera property tree for :class:`~QVideo.cameras.Genicam.QGenicamCamera`.

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

    def __init__(self, *args,
                 camera: Source,
                 visibility: EVisibility = EVisibility.Guru,
                 controls: list[str] | None = None,
                 **kwargs) -> None:
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
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._pollCamera)
        self._timer.start()
        quitting = QtCore.QCoreApplication.instance().aboutToQuit
        quitting.connect(self._timer.stop)

    def closeEvent(self, event) -> None:
        self._timer.stop()
        super().closeEvent(event)

    def description(self, camera: QGenicamCamera) -> dict:
        '''Return a dictionary describing the node map of the camera'''
        root = camera.node('Root')
        if root is None:
            return []
        description = self.describe(root)
        return description.get('children', [])

    def describe(self, feature: IValue) -> dict[str, object]:
        '''Return a dictionary describing the specified feature'''
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
            this['value'] = this['default'] = feature.value
            this['min'] = feature.min
            this['max'] = feature.max
            this['units'] = feature.unit
            if feature.has_inc():
                this['step'] = feature.inc
        elif isinstance(feature, IString):
            this['type'] = 'str'
            this['value'] = this['default'] = feature.value
        else:
            # FIXME: Support for IRegister nodes
            logger.debug(
                f'Unsupported node type: {feature.node.name}: {type(feature)}')
        return this

    def _connectSignals(self) -> None:
        super()._connectSignals()
        for item in self.listAllItems():
            p = item.param
            p.sigValueChanged.connect(self._handleItemChanges)

    def _handleItemChanges(self) -> None:
        if self._ignoreSync:
            return
        logger.debug('Handling item changes')
        self._updateVisible()
        self._updateEnabled()
        self._updateLimits()
        self._updateValues()

    def _updateVisible(self) -> None:
        for item in self.listAllItems()[1:]:
            p = item.param
            p.setOpts(visible=self.visible(p))

    def visible(self, param) -> bool:
        ptype = param.opts['type']
        if ptype in ('action', None):
            return False
        if ptype == 'group':
            return any(self.visible(c) for c in param.children())
        visibility = param.opts.get('visibility', EVisibility.Invisible)
        return visibility <= self.visibility

    def _updateEnabled(self) -> None:
        for item in self.listAllItems()[1:]:
            p = item.param
            if p.opts.get('visible', False):
                name = p.opts['name']
                if self.camera.has_node(name):
                    p.setOpts(enabled=self.camera.is_readwrite(name))

    def _updateValues(self) -> None:
        '''Refresh read-only Parameter values from the live GenICam node map.

        Called after every property change so that derived read-only nodes
        (e.g. ``AcquisitionResultingFrameRate``) reflect the current hardware
        state in the UI.  Only visible read-only leaf parameters are updated.
        Signals are blocked during the update to prevent re-entrant calls.
        '''
        for item in self.listAllItems()[1:]:
            p = item.param
            if not p.opts.get('visible', False):
                continue
            name = p.opts.get('name')
            if not self.camera.has_node(name):
                continue
            node = self.camera.node(name)
            if node.node.get_access_mode() != EAccessMode.RO:
                continue
            if isinstance(node, IEnumeration):
                value = node.to_string()
            elif isinstance(node, (IBoolean, IInteger, IFloat, IString)):
                value = node.value
            else:
                continue
            p.blockSignals(True)
            try:
                p.setValue(value)
            finally:
                p.blockSignals(False)

    def _pollCamera(self) -> None:
        '''Refresh all readable Parameter values and enabled states.

        Called by the poll timer to pick up autonomous camera-side changes
        that do not generate host-side notifications — e.g. ``Gain`` being
        adjusted during auto-exposure, or ``GainAuto`` reverting from
        ``"Once"`` to ``"Off"`` after the sweep completes.

        Returns immediately if the camera is no longer open(e.g. during
        application shutdown) to prevent accessing freed C++ genapi objects.

        Signals are not blocked so that the visual widgets update and
        ``_handleItemChanges`` fires when a value changes.
        : attr: `_ignoreSync` is set for the duration so that the resulting
        ``sigTreeStateChanged`` emissions do not send values back to the
        camera.: meth: `_updateEnabled` is called unconditionally so that
        access-mode changes(e.g. ``ExposureTime`` becoming writable again
        after the sweep) are reflected even when the controlling node value
        has not changed.
        '''
        if not self.camera.isOpen():
            return
        self._ignoreSync = True
        try:
            self._updateLimits()
            for item in self.listAllItems()[1:]:
                p = item.param
                if not p.opts.get('visible', False):
                    continue
                name = p.opts.get('name')
                if not self.camera.has_node(name):
                    continue
                node = self.camera.node(name)
                mode = node.node.get_access_mode()
                if mode not in (EAccessMode.RO, EAccessMode.RW):
                    continue
                if isinstance(node, IEnumeration):
                    value = node.to_string()
                elif isinstance(node, (IBoolean, IInteger, IFloat, IString)):
                    value = node.value
                else:
                    continue
                p.setValue(value)
            self._updateEnabled()
        finally:
            self._ignoreSync = False

    def _updateLimits(self) -> None:
        '''Refresh Parameter constraints from the live GenICam node values.

        Called after every property change so that dependent nodes(e.g.
        ``OffsetX`` range after a ``Width`` change) reflect the current
        hardware state in the UI.  Only visible leaf parameters are updated.
        '''
        for item in self.listAllItems()[1:]:
            p = item.param
            if not p.opts.get('visible', False):
                continue
            name = p.opts.get('name')
            if not self.camera.has_node(name):
                continue
            node = self.camera.node(name)
            if isinstance(node, IInteger):
                p.setOpts(limits=(node.min, node.max), step=node.inc)
            elif isinstance(node, IFloat):
                opts = {'limits': (node.min, node.max)}
                if node.has_inc():
                    opts['step'] = node.inc
                p.setOpts(**opts)
            elif isinstance(node, IEnumeration):
                p.setOpts(limits=[v.symbolic for v in node.entries])

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


if __name__ == '__main__':  # pragma: no cover
    QGenicamTree.example()
