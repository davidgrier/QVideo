from QVideo.lib import QCamera
from pyqtgraph.Qt.QtCore import (pyqtProperty, pyqtSlot, QMutexLocker)
from genicam.genapi import (IValue, EAccessMode, EVisibility,
                            ICategory, ICommand, IEnumeration,
                            IBoolean, IInteger, IFloat, IString)
from genicam.gentl import TimeoutException
from harvesters.core import Harvester
import logging


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


READABLE = (EAccessMode.RO, EAccessMode.RW)
WRITEABLE = (EAccessMode.WO, EAccessMode.RW)


def _todict(feature: IValue) -> dict:
    '''Return a dictionary describing the node map'''
    this = dict(name=feature.node.name,
                title=feature.node.display_name,
                visibility=feature.node.visibility)
    mode = feature.node.get_access_mode()
    if mode == EAccessMode.NI:
        return this
    if isinstance(feature, ICategory):
        this['type'] = 'group'
        this['children'] = [_todict(f) for f in feature.features]
        return this
    if isinstance(feature, ICommand):
        this['type'] = 'action'
        return this
    if mode not in READABLE:
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


def _flatten(d: dict) -> list[dict]:
    this = []
    if d.get('type', None) == 'group':
        for c in d['children']:
            this.extend(_flatten(c))
    else:
        this.extend([d])
    return this


def _properties(feature: IValue) -> list[str]:
    '''Return names of accessible properties'''
    this = []
    if isinstance(feature, ICategory):
        for f in feature.features:
            this.extend(_properties(f))
    elif isinstance(feature, (IEnumeration, IBoolean, IInteger, IFloat)):
        if feature.node.get_access_mode() == EAccessMode.RW:
            this = [feature.node.name]
    return this


def _methods(feature: IValue) -> list[str]:
    '''Return names of executable methods'''
    this = []
    if isinstance(feature, ICategory):
        for f in feature.features:
            this.extend(_methods(f))
    elif isinstance(feature, ICommand):
        this = [feature.node.name]
    return this


def _modes(feature: IValue) -> dict[str, int]:
    '''Return access modes of all camera settings'''
    modes = dict()
    if isinstance(feature, ICategory):
        for f in feature.features:
            modes.update(_modes(f))
    elif isinstance(feature, (IEnumeration, IBoolean, IInteger, IFloat)):
        name = feature.node.name
        mode = feature.node.get_access_mode()
        modes[name] = mode
    return modes


def _set(feature: IValue, value: bool | int | float | str):
    '''Set the value of a feature'''
    mode = feature.node.get_access_mode()
    if mode not in WRITEABLE:
        logger.info(f'{feature.node.name} is not writeable')
        return
    logger.debug(f'Setting {feature.node.name}: {value}')
    if isinstance(feature, IEnumeration):
        feature.from_string(value)
    else:
        feature.value = value


def _get(feature: IValue) -> bool | int | float | str | None:
    '''Return the value of a feature'''
    mode = feature.node.get_access_mode()
    if mode not in READABLE:
        logger.info('f{feature.node.name} is not readable')
        return None
    logger.debug(f'Getting {feature.node.name}')
    if isinstance(feature, IEnumeration):
        return feature.to_string()
    else:
        return feature.value


class QGenicamCamera(QCamera):

    def __init__(self, producer: str, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.harvester = Harvester()
        self.harvester.add_file(producer)
        self.harvester.update()
        self.open()

    def _initialize(self) -> bool:
        self.device = self.harvester.create()
        try:
            self.node_map = self.device.remote_device.node_map
            self.name = self.node_map.DeviceModelName.value
            root = self.node()
            self._properties = _properties(root)
            self._methods = _methods(root)
            ma = _modes(root)
            self.device.start()
            mb = _modes(root)
            self.protected = [k for k, v in ma.items() if mb[k] != v]
        finally:
            return self.device.is_valid()
        '''
        FIXME: Handle exceptions
        '''

    def _deinitialize(self) -> None:
        self.device.stop()
        self.device.destroy()

    def read(self) -> QCamera.CameraData:
        frame = None
        try:
            with self.device.fetch(timeout=1) as buffer:
                image = buffer.payload.components[0]
                height = image.height
                width = image.width
                channels = int(image.num_components_per_pixel)
                frame = image.data.copy()
            frame = frame.reshape(height, width, channels).squeeze()
        except TimeoutException:
            logger.warning('camera acquisition timed out')
        return frame is not None, frame

    def node(self, name: str = 'Root') -> IValue | None:
        if self.node_map.has_node(name):
            return self.node_map.get_node(name)
        else:
            return None

    def readable(self, name: str) -> bool:
        return self.node(name).get_access_mode() in READABLE

    def writeable(self, name: str) -> bool:
        return self.node(name).get_access_mode() in WRITEABLE

    def accessible(self, name: str) -> bool:
        return self.node(name).get_access_mode() == EAccessMode.RW

    def readonly(self, name: str) -> bool:
        return self.node(name).get_access_mode() == EAccessMode.RO

    @pyqtSlot(str, object)
    def set(self, key: str, value) -> None:
        '''Set named property'''
        if (feature := self.node(key)):
            restart = key in self.protected and self.device.is_acquiring()
            with QMutexLocker(self.mutex):
                logger.debug(f'setting {key}: {value} ({restart})')
                if restart:
                    self.device.stop()
                _set(feature, value)
                if restart:
                    self.device.start()

    @pyqtSlot(str)
    def get(self, key: str) -> QCamera.PropertyValue | None:
        '''Get named property'''
        value = None
        if (feature := self.node(key)):
            with QMutexLocker(self.mutex):
                value = _get(feature)
                logger.debug(f'getting {key}: {value}')
                self.propertyValue.emit(key, value)
        return value

    @pyqtSlot(str)
    def execute(self, key: str) -> None:
        '''Execute named method'''
        if (feature := self.node(key)) and isinstance(feature, ICommand):
            with QMutexLocker(self.mutex):
                logger.debug(f'executing {feature}')
                feature.execute()

    @pyqtProperty(int)
    def width(self) -> int:
        return int(self.node_map.Width.value)

    @pyqtProperty(int)
    def height(self) -> int:
        return int(self.node_map.Height.value)

    def properties(self) -> list[str]:
        return self._properties

    def methods(self) -> list[str]:
        return self._methods

    def description(self,
                    root: str = 'Root',
                    controls: list[str] | None = None,
                    flatten: bool = False) -> list[dict]:
        # print(name=self.get('DeviceModelName'))
        root = _todict(self.node(root))
        if controls is not None:
            return [c for c in _flatten(root) if c['name'] in controls]
        return _flatten(root) if flatten else root['children']


def example():
    # QGenicamCamera.example()
    # from pprint import pprint

    cam = QGenicamCamera()
    cam.set('Gamma', 0.8)
    print(f"Gamma: {cam.get('Gamma')}")
    flip = cam.get('ReverseY')
    cam.set('ReverseY', not flip)
    print(f"ReverseY: {cam.get('ReverseY')}")


def showtree():
    from pyqtgraph.Qt.QtWidgets import QApplication
    import sys
    from pyqtgraph.parametertree import (Parameter, ParameterTree)

    cam = QGenicamCamera()
    params = cam.description()['children']
    name = cam.name

    app = QApplication(sys.argv)
    tree = ParameterTree()
    params = Parameter.create(name=name, type='group', children=params)
    tree.setParameters(params)
    tree.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    # showtree()
    example()
