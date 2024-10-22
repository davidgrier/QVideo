from QVideo.lib import QCamera
import PySpin
from PyQt5.QtCore import (pyqtSignal, pyqtProperty, pyqtSlot)
from typing import (TypeAlias, Union, Callable)
import logging


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


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

    def Property(ptype, name: str, stop: bool = False, shape: bool = False) -> Callable:

        logger.debug(f'Registering {name}')

        def getter(inst) -> Value:
            logger.debug(f'Getting {name}')
            value = None
            try:
                node = getattr(inst.device, name)
                if PySpin.IsAvailable(node) and PySpin.IsReadable(node):
                    if isinstance(node, PySpin.IEnumeration):
                        value = node.ToString()
                    else:
                        value = node.GetValue()
                else:
                    logger.warning(f'{name} is not readable')
            except PySpin.SpinnakerException as ex:
                logger.error(f'Error getting {name}: {ex}')
            return value

        def setter(inst, value: Value) -> None:
            logger.debug(f'Setting {name}: {value}')
            try:
                if stop:
                    inst.pause()
                node = getattr(inst.device, name)
                if not (PySpin.IsAvailable(node) and PySpin.IsWritable(node)):
                    logger.warning(f'{name} is not writable')
                    return
                if isinstance(node, PySpin.IEnumeration):
                    node.FromString(value)
                else:
                    if isinstance(node, (PySpin.IInteger, PySpin.IFloat)):
                        vmin = node.GetMin()
                        vmax = node.GetMax()
                        clipped = min(max(value, vmin), vmax)
                        if clipped != value:
                            logger.warning(f'{value} is out of range for {name}')
                            value = clipped
                    node.SetValue(value)
                inst.valueChanged.emit(name)
                if shape:
                    inst.shapeChanged.emit(inst.shape)
                if stop:
                    inst.resume()
            except PySpin.SpinnakerException as ex:
                logger.error(f'Error setting {name}: {ex}')

        return pyqtProperty(ptype, getter, setter)

    def Trigger(name) -> Callable:
        @pyqtSlot(bool)
        def slot(inst, state) -> None:
            node = getattr(inst.device, name)
            if (PySpin.IsAvailable(node) and PySpin.IsWritable(node)):
                node.FromString('Once')
            else:
                logger.warning(f'Could not trigger {name}')
        return slot

    valueChanged = pyqtSignal(str)

    acquisitionframecount = Property(int, 'AcquisitionFrameCount')
    acquisitionframerate = Property(float, 'AcquisitionFrameRate')
    acquisitionframerateenable = Property(bool, 'AcquisitionFrameRateEnable')
    acquisitionmode = Property(str, 'AcquisitionMode')
    adcbitdepth = Property(str, 'AdcBitDepth')
    autoexposurecontrolpriority = Property(str, 'AutoExposureControlPriority')
    blacklevel = Property(float, 'BlackLevel')
    blacklevelselector = Property(str, 'BlackLevelSelector')
    devicefirmwareversion = Property(str, 'DeviceFirmwareVersion')
    devicemodelname = Property(str, 'DeviceModelName')
    deviceserialnumber = Property(str, 'DeviceSerialNumber')
    devicevendorname = Property(str, 'DeviceVendorName')
    exposureauto = Property(str, 'ExposureAuto')
    exposuremode = Property(str, 'ExposureMode')
    exposuretime = Property(float, 'ExposureTime')
    exposuretimemode = Property(str, 'ExposureTimeMode')
    gain = Property(float, 'Gain')
    gainauto = Property(str, 'GainAuto')
    gamma = Property(float, 'Gamma')
    gammaenable = Property(bool, 'GammaEnable')
    height = Property(int, 'Height', shape=True)
    heightmax = Property(int, 'HeightMax')
    offsetx = Property(int, 'OffsetX', stop=True)
    offsety = Property(int, 'OffsetY', stop=True)
    pixelformat = Property(str, 'PixelFormat', stop=True)
    reversex = Property(bool, 'ReverseX', stop=True)
    reversey = Property(bool, 'ReverseY', stop=True)
    sharpening = Property(float, 'Sharpening', stop=True)
    sharpeningauto = Property(bool, 'SharpeningAuto')
    sharpeningenable = Property(bool, 'SharpeningEnable')
    sharpeningthreshold = Property(float, 'SharpeningThreshold')
    width = Property(int, 'Width', shape=True)
    widthmax = Property(int, 'WidthMax')

    flipped = Property(bool, 'ReverseY', stop=True)
    mirrored = Property(bool, 'ReverseX', stop=True)

    autoexposure = Trigger('ExposureAuto')
    autogain = Trigger('GainAuto')
    autosharpening = Trigger('SharpeningAuto')

    def __init__(self, *args,
                 cameraID: int = 0,
                 mirrored: bool = True,
                 flipped: bool = False,
                 gray: bool = True,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.cameraID = cameraID
        self.open()
        self._refineProperties()
        self._setDefaults()
        self._testColor()
        self.flipped = flipped
        self.mirrored = mirrored
        self.gray = gray

    def initialize(self) -> bool:
        '''
        Initialize Spinnaker and open camera specified by cameraID

        Returns
        -------
        success: bool
            True: the camera is open and can read frames
            False: failure opening camera.
        '''
        self.device = None
        self._system = PySpin.System.GetInstance()
        self._devices = self._system.GetCameras()
        ncameras = self._devices.GetSize()
        if self.cameraID in range(ncameras):
            self.device = self._devices[self.cameraID] # .GetByIndex(self.cameraID)
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

    def deinitialize(self) -> None:
        '''Stop acquisition, close camera and release Spinnaker'''
        logger.debug('Closing')
        if self.device is not None:
            logger.debug('... device')
            if self.device.IsStreaming():
                self.device.EndAcquisition()
            self.device = None
        if hasattr(self, '_devices'):
            logger.debug('... device list')
            self._devices.Clear()
            self._device = None
        if hasattr(self, '_system'):
            if not self._system.IsInUse():
                logger.debug('... system')
                self._system.ReleaseInstance()
                self._system = None

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
        if self._color_capable:
            self.pixelformat = 'Mono8' if gray else 'RGB8Packed'

    @pyqtProperty(str)
    def version(self) -> str:
        v = self._system.GetLibraryVersion()
        s = f'{v.major}.{v.minor}.{v.type}.{v.build}'
        logger.debug(f'PySpin version: {s}')
        return s

    def colorCapable(self) -> bool:
        return self._color_capable

    def _refineProperties(self) -> None:
        for p in self.properties():
            if getattr(self, p) is None:
                self._properties.remove(p)

    def _testColor(self) -> None:
        level = logger.level
        logger.setLevel(logging.CRITICAL)
        if self.pixelformat == 'RGB8Packed':
            self._color_capable = True
        else:
            try:
                self.pixelformat = 'RGB8Packed'
                self._color_capable = True
            except PySpin.SpinnakerException:
                self._color_capable = False
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


def example() -> None:
    from pprint import pprint

    logger.setLevel(logging.ERROR)

    camera = QSpinnakerCamera()
    print(camera.cameraname)
    print(f'Serial number: {camera.deviceserialnumber}')
    print('Settings:')
    pprint(camera.settings())
    camera.close()


if __name__ == '__main__':
    example()
