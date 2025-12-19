from QVideo.lib import (QCamera, QVideoSource)
from pyqtgraph.Qt.QtCore import (pyqtProperty, pyqtSlot, QMutexLocker)
import numpy as np
import logging
try:
    from harvesters.core import Harvester
    from genicam.genapi import (IValue, EAccessMode, EVisibility,
                                ICategory, ICommand, IEnumeration,
                                IBoolean, IInteger, IFloat, IString)
    from genicam.gentl import TimeoutException
except (ImportError, ModuleNotFoundError) as error:
    Harvester = None


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


__all__ = ['QGenicamCamera', 'QGenicamSource']


def _properties(feature: IValue) -> list[str]:
    '''Return names of accessible properties'''
    this = []
    if isinstance(feature, ICategory):
        for f in feature.features:
            this.extend(_properties(f))
    elif isinstance(feature, (IEnumeration, IBoolean, IInteger, IFloat)):
        accessmode = feature.node.get_access_mode()
        if accessmode in (EAccessMode.RO, EAccessMode.RW):
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


def _set(feature: IValue, value: QCamera.PropertyValue):
    '''Set the value of a feature'''
    mode = feature.node.get_access_mode()
    if mode not in (EAccessMode.RW, EAccessMode.WO):
        logger.info(f'{feature.node.name} is not writeable')
        return
    logger.debug(f'Setting {feature.node.name}: {value}')
    if isinstance(feature, IEnumeration):
        if value in [v.symbolic for v in feature.entries]:
            feature.from_string(value)
        else:
            logger.warning(f'{value} is not in {feature.name}')
    elif isinstance(feature, IBoolean):
        feature.value = bool(value)
    elif isinstance(feature, IInteger):
        value = np.clip(value, feature.min, feature.max)
        value = (value - feature.min) // feature.inc
        feature.value = int(value * feature.inc + feature.min)
    elif isinstance(feature, IFloat):
        feature.value = float(np.clip(value, feature.min, feature.max))
    elif isinstance(feature, IString):
        feature.value = str(value)


def _get(feature: IValue) -> QCamera.PropertyValue | None:
    '''Return the value of a feature'''
    accessmode = feature.node.get_access_mode()
    if accessmode not in (EAccessMode.RW, EAccessMode.RO):
        logger.info('f{feature.node.name} is not readable')
        return None
    logger.debug(f'Getting {feature.node.name}')
    if isinstance(feature, IEnumeration):
        return feature.to_string()
    else:
        return feature.value


class QGenicamCamera(QCamera):
    '''Base class for cameras implementing the GenICam standard

    GenICam is a standardized machine-vision interface maintained
    by the European Machine Vision Association
    https://www.emva.org/standards-technology/genicam/

    Requirements
    ------------
    > pip install genicam
    > pip install harvesters

    Connecting to a specific GenICam camera requires a "GenTL producer",
    which is a binary file that implements communications between
    the host computer and the camera. The producer typically is
    provided by the manufacturer of the camera is is a file with
    a ".cti" extension. Manufacturers may provide different versions
    of the cti file for different operating systems and for different
    versions of python.

    Inherits
    --------
    QVideo.lib.QCamera

    Properties
    ----------
    producer : str
        Path to GenTL producer file
    cameraID : int
        Index of camera to use (default 0)
    '''

    def __init__(self, producer: str,
                 *args,
                 cameraID: int = 0,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.producer = producer
        self.cameraID = cameraID
        self.open()

    def _initialize(self) -> bool:
        if Harvester is None:
            logger.warning('''
            Could not import harvesters library:
            Genicam camera support is not available''')
            return False
        self.harvester = Harvester()
        self.harvester.add_file(self.producer)
        self.harvester.update()
        try:
            self.device = self.harvester.create(self.cameraID)
        except ValueError:
            logger.warning('No camera was found')
            return False
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

    def _deinitialize(self) -> None:
        self.device.stop()
        self.device.destroy()
        self.harvester.reset()

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
            logger.debug(f'node {name} is unknown')
            return None

    @pyqtSlot(str, object)
    def set(self, key: str, value) -> None:
        '''Set named property'''
        if (feature := self.node(key)) is not None:
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

    def is_readwrite(self, feature: str) -> bool:
        mode = self.node(feature).node.get_access_mode()
        return (mode == EAccessMode.RW) or (feature in self.protected)

    @pyqtProperty(int)
    def width(self) -> int:
        return self.get('Width')

    @width.setter
    def width(self, width: int) -> None:
        self.set('Width', width)
        self.shapeChanged.emit(self.shape)

    @pyqtProperty(int)
    def height(self) -> int:
        return self.get('Height')

    @height.setter
    def height(self, height: int) -> None:
        self.set('Height', height)
        self.shapeChanged.emit(self.shape)

    @pyqtProperty(float)
    def fps(self) -> float:
        return self.get('AcquistionResultingFrameRate')

    @fps.setter
    def fps(self, fps: float) -> None:
        self.set('AcquisitionFrameRate', fps)

    def properties(self) -> list[str]:
        return self._properties

    def methods(self) -> list[str]:
        return self._methods


class QGenicamSource(QVideoSource):

    '''Base class for video sources using GenICam cameras

    Inherits
    --------
    QVideo.lib.QVideoSource
    '''

    def __init__(self, *args,
                 camera: QGenicamCamera | None = None,
                 **kwargs) -> None:
        camera = camera or QGenicamCamera(*args, **kwargs)
        super().__init__(camera, *args, **kwargs)


if __name__ == '__main__':
    QGenicamCamera.example()
