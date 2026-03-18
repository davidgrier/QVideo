from QVideo.lib import QCamera
from PyQt5.QtCore import (pyqtSignal, pyqtProperty, pyqtSlot)
from typing import (TypeAlias, Union, Callable)
import logging


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


try:
    import PySpin
    HAS_SPINNAKER = True
except ImportError as ex:
    logger.error(f'Could not import PySpin API: {ex}')
    HAS_SPINNAKER = False


Value: TypeAlias = Union[bool, int, float, str]


'''
Technical Reference:
http://softwareservices.flir.com/BFS-U3-123S6/latest/Model/public/index.html

NOTE:
USB 3.x communication on Ubuntu 16.04 through 20.04 requires
> sudo sh -c 'echo 1000 > /sys/module/usbcore/parameters/usbfs_memory_mb'

This can be set permanently by
1. Editing /etc/default/grub
Change:
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"
to:
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash usbcore.usbfs_memory_mb=1000"
2. > sudo update-grub
3. > sudo reboot now
'''


def _todict(feature: PySpin.IValue) -> dict:
    '''Return a dictionary describing the node map'''
    this = dict(name=feature.GetName(),
                title=feature.GetDisplayName())
    if not PySpin.IsImplemented(feature):
        this['visible'] = False
        return this
    if isinstance(feature, PySpin.ICategory):
        this['type'] = 'group'
        this['children'] = [_todict(f) for f in feature.features]
        return this
    if isinstance(feature, ICommand):
        this['type'] = 'action'
        return this
    if mode not in READABLE:
        this['visible'] = False
        return this
    this['enabled'] = (mode == EAccessMode.RW)
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
        logger.debug(
            f'Unsupported node type: {feature.node.name}: {type(feature)}')
    return this


def _properties(feature: PySpin.IValue) -> list[str]:
    '''Return a list of accessible properties'''
    this = []
    if isinstance(feature, PySpin.ICategory):
        for f in feature.features:
            this.extend(_properties(f))
    elif isinstance(feature, (PySpin.IEnumeration,
                              PySpin.IBoolean,
                              PySpin.IInteger,
                              PySpin.IFloat)):
        if feature.node.get_access_mode() == EAccessMode.RW:
            this = [feature.node.name]
    return this


def _methods(feature: PySpin.IValue) -> list[str]:
    '''Return a list of executable methods'''
    this = []
    if isinstance(feature, PySpin.ICategory):
        for f in feature.features:
            this.extend(_methods(f))
    elif isinstance(feature, PySpin.ICommand):
        this = [feature.node.name]
    return this


def _set(feature: PySpin.IValue, value: bool | int | float | str):
    '''Set the value of a feature'''
    mode = feature.node.get_access_mode()
    if mode not in WRITEABLE:
        return
    if isinstance(feature, PySpin.IEnumeration):
        feature.from_string(value)
    else:
        feature.value = value


def _get(feature: PySpin.IValue) -> bool | int | float | str | None:
    '''Return the value of a feature'''
    mode = feature.node.get_access_mode()
    if mode not in READABLE:
        return None
    if isinstance(feature, PySpin.IEnumeration):
        return feature.to_string()
    else:
        return feature.value


class QSpinnakerCamera(QCamera):

    '''Expose properties of FLiR camera

    ...

    Properties
    ==========
    device: PySpin.CameraPtr
        camera device in Spinnaker system
    cameraname : str
        Vendor and camera model

    Methods
    =======
    open(index) :
        Open FLiR camera specified by index
        Default: index=0, first camera
    close() :
        Close camera
    start() :
        Start image acquisition
    stop() :
        Stop image acquisition
    read() : (bool, numpy.ndarray)
        Return a tuple containing the status of the acquisition
        and the next available video frame
        status: True if acquisition was successful
        frame: numpy ndarray containing image information
    '''

    def __init__(self, *args,
                 cameraID: int = 0,
                 mirrored: bool = True,
                 flipped: bool = False,
                 gray: bool = True,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.cameraID = cameraID
        self.open()

    def _initialize(self) -> bool:
        '''
        Initialize Spinnaker and open camera specified by cameraID

        Returns
        -------
        success: bool
            True: the camera is open and can read frames
            False: failure opening camera.
        '''
        if not HAS_SPINNAKER:
            return False
        self.device = None
        self._system = PySpin.System.GetInstance()
        self._devices = self._system.GetCameras()
        ncameras = self._devices.GetSize()
        if self.cameraID in range(ncameras):
            self.device = self._devices[self.cameraID]
        else:
            logger.error(f'Camera {self.cameraID} not found')
            return False
        if not self.device.IsValid():
            logger.error(f'Camera {self.cameraID} is not valid')
            return False
        if not self.device.IsInitialized():
            self.device.Init()
        self.acquisitionmode = 'Continuous'
        self.device.BeginAcquisition()
        logger.debug(f'Camera {self.cameraID} open')
        return True

    def _deinitialize(self) -> None:
        '''Stop acquisition, close camera and release Spinnaker'''
        logger.debug('Closing')
        if self.device is not None:
            logger.debug('... device')
            if self.device.IsStreaming():
                self.device.EndAcquisition()
            self.device.DeInit()
            del self.device
        if hasattr(self, '_devices'):
            logger.debug('... device list')
            self._devices.Clear()
        if hasattr(self, '_system'):
            if not self._system.IsInUse():
                logger.debug('... system')
                self._system.ReleaseInstance()

    @pyqtSlot()
    def pause(self) -> None:
        if self.isOpen() and self.device.IsStreaming():
            logger.debug('pausing')
            self.device.EndAcquisition()

    @pyqtSlot()
    def resume(self) -> None:
        if self.isOpen() and not self.device.IsStreaming():
            logger.debug('resuming')
            self.device.BeginAcquisition()

    def read(self) -> QCamera.CameraData:
        try:
            frame = self.device.GetNextImage()
            return True, frame.GetNDArray()
        except PySpin.SpinnakerException as ex:
            logger.error(f'Error reading frame: {ex}')
            return False, None

    @pyqtProperty(str)
    def cameraname(self) -> str:
        return f'{self.devicevendorname} {self.devicemodelname}'

    @pyqtProperty(bool)
    def gray(self) -> bool:
        return self.pixelformat == 'Mono8'

    @gray.setter
    def gray(self, gray: bool) -> None:
        logger.debug(f'Setting Gray: {gray}')
        if self._colorCapable:
            self.pixelformat = 'Mono8' if gray else 'RGB8Packed'

    @pyqtProperty(str)
    def version(self) -> str:
        v = self._system.GetLibraryVersion()
        s = f'{v.major}.{v.minor}.{v.type}.{v.build}'
        logger.debug(f'PySpin version: {s}')
        return s

    @pyqtProperty(float)
    def fps(self) -> float:
        return self.acquisitionframerate

    def colorCapable(self) -> bool:
        return self._colorCapable

    def _refineProperties(self) -> None:
        for p in self.properties():
            if getattr(self, p) is None:
                self._properties.remove(p)

    def _testColor(self) -> None:
        level = logger.level
        logger.setLevel(logging.CRITICAL)
        if self.pixelformat == 'RGB8Packed':
            self._colorCapable = True
        else:
            try:
                self.pixelformat = 'RGB8Packed'
                self._colorCapable = True
            except PySpin.SpinnakerException:
                self._colorCapable = False
            self.pixelformat = 'Mono8'
        logger.setLevel(level)

    def _setDefaults(self) -> None:
        self.acquisitionframerateenable = True
        self.blacklevelselector = 'All'
        self.gammaenable = True
        self.gamma = 1.
        self.sharpeningenable = False
        self.autoexposurecontrolpriority = 'Gain'
        self.exposureauto = 'Off'
        self.exposuremode = 'Timed'
        self.exposuretimemode = 'Common'
        self.gainauto = 'Off'
        self.sharpeningauto = 'Off'


if __name__ == '__main__':
    QSpinnakerCamera.example()
