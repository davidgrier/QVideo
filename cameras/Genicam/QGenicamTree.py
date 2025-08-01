from pyqtgraph.Qt.QtCore import (pyqtProperty, pyqtSlot, QVariant)
from QVideo.lib import QCameraTree
from QVideo.cameras.Genicam import QGenicamCamera
from genicam.genapi import (IValue, EAccessMode, EVisibility,
                            ICategory, ICommand, IEnumeration,
                            IBoolean, IInteger, IFloat, IString)
import logging


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class QGenicamTree(QCameraTree):

    def __init__(self, *args,
                 camera: QCameraTree.Source | None = None,
                 visibility: EVisibility = EVisibility.Guru,
                 controls: list[str] | None = None,
                 **kwargs) -> None:
        camera = camera or QGenicamCamera(*args, **kwargs)
        description = self.description(camera)
        super().__init__(camera, description, *args, **kwargs)
        self.controls = controls
        self.visibility = visibility
        self._updateEnabled()

    def description(self, camera: QGenicamCamera) -> dict:
        '''Return a dictionary describing the node map of the camera'''
        root = camera.node('Root')
        description = self.describe(root)
        return description['children']

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
            '''FIXME: Support for IRegister nodes'''
            logger.debug(
                f'Unsupported node type: {feature.node.name}: {type(feature)}')
        return this

    def _connectSignals(self) -> None:
        super()._connectSignals()
        for item in self.listAllItems():
            p = item.param
            p.sigValueChanged.connect(self._handleItemChanges)

    @pyqtSlot()
    def _handleItemChanges(self) -> None:
        logger.debug('Handling item changes')
        self._updateVisible()
        self._updateEnabled()

    def _updateVisible(self) -> None:
        for item in self.listAllItems()[1:]:
            p = item.param
            p.setOpts(visible=self.visible(p))

    def visible(self, param: dict | list[dict]) -> bool | list[bool]:
        if isinstance(param, list):
            return [self.visible(p) for p in param]
        ptype = param.opts['type']
        if ptype in ('action', None):
            return False
        if ptype == 'group':
            return any(self.visible(param.children()))
        visibility = param.opts.get('visibility', EVisibility.Invisible)
        return visibility <= self.visibility

    def _updateEnabled(self) -> None:
        for item in self.listAllItems()[1:]:
            p = item.param
            if p.opts.get('visible', False):
                name = p.opts['name']
                p.setOpts(enabled=self.camera.is_readwrite(name))

    @pyqtProperty(QVariant)
    def controls(self) -> list[str] | None:
        return self._controls

    @controls.setter
    def controls(self, controls: list[str] | None) -> None:
        self._controls = controls
        for item in self.listAllItems()[1:]:
            p = item.param
            name = p.opts['name']
            if (controls is None) or (name in controls):
                visibility = self.camera.node(name).node.visibility
            else:
                visibility = EVisibility.Invisible
            p.opts['visibility'] = visibility

    @pyqtProperty(EVisibility)
    def visibility(self) -> EVisibility:
        return self._visibility

    @visibility.setter
    def visibility(self, visibility: EVisibility) -> None:
        self._visibility = visibility
        self._updateVisible()


if __name__ == '__main__':
    QGenicamTree.example()
