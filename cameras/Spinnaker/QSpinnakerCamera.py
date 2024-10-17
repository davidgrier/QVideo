from QVideo.lib import QCamera
import PySpin
from PyQt5.QtCore import (pyqtSignal, pyqtProperty, pyqtSlot)
from typing import (TypeAlias, Union, Callable)
import logging


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


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

    def Property(ptype, name: str, stop: bool = False) -> Callable:

        logger.debug(f'Registering {name}')

        def getter(inst) -> Value:
            logger.debug(f'Getting {name}')
            value = None
            try:
                feature = getattr(inst.device, name)
                if PySpin.IsAvailable(feature) and PySpin.IsReadable(feature):
                    if isinstance(feature, PySpin.IEnumeration):
                        value = feature.ToString()
                    else:
                        value = feature.GetValue()
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
                feature = getattr(inst.device, name)
                if not (PySpin.IsAvailable(feature) and PySpin.IsWritable(feature)):
                    logger.warning(f'{name} is not writable')
                    return
                if isinstance(feature, PySpin.IEnumeration):
                    feature.FromString(value)
                else:
                    if isinstance(feature, (PySpin.IInteger, PySpin.IFloat)):
                        vmin = feature.GetMin()
                        vmax = feature.GetMax()
                        clipped = min(max(value, vmin), vmax)
                        if clipped != value:
                            logger.warning(f'{value} is out of range for {name}')
                            value = clipped
                    feature.SetValue(value)
                if stop:
                    inst.resume()
                inst.propertyChanged.emit(name)
            except PySpin.SpinnakerException as ex:
                logger.error(f'Error setting {name}: {ex}')

        return pyqtProperty(ptype, getter, setter)

    def Trigger(name) -> Callable:
        @pyqtSlot(bool)
        def slot(inst, state) -> None:
            feature = getattr(inst.device, name)
            if PySpin.IsWritable(feature):
                feature.FromString('Once')
            else:
                logger.warning(f'Could not trigger {name}')
        return slot

    propertyChanged = pyqtSignal(str)

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
        self._testColor()
        self._refineProperties()
        self.setDefaults()
        self.flipped = flipped
        self.mirrored = mirrored
        self.gray = gray
        _, frame = self.read()

    def initialize(self) -> bool:
        '''
        Initialize Spinnaker and open specified camera

        Keywords
        --------
        cameraID: int
            Index of camera to open. Default: 0
        '''
        self.device = None
        self._system = PySpin.System.GetInstance()
        self._devices = self._system.GetCameras()
        ncameras = self._devices.GetSize()
        if self.cameraID in range(ncameras):
            self.device = self._devices.GetByIndex(self.cameraID)
        else:
            logger.error(f'Camera {self.cameraID} not found')
            return False
        if not self.device.IsValid():
            logger.error(f'Camera {self.cameraID} is not valid')
            return False
        if not self.device.IsInitialized():
            self.device.Init()
        self.device.BeginAcquisition()
        logger.debug(f'Camera {self.cameraID} open')
        return True

    def deinitialize(self) -> None:
        '''Stop acquisition, close camera and release Spinnaker'''
        logger.debug('Closing')
        if hasattr(self, 'device'):
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
            self.device.EndAcquisition()

    @pyqtSlot()
    def resume(self) -> None:
        if self.isOpen() and not self.device.IsStreaming():
            self.device.BeginAcquisition()

    def read(self) -> tuple[bool, 'np.ndarray']:
        '''The whole point of the thing: Gimme da piccy'''
        try:
            frame = self.device.GetNextImage()
            return True, frame.GetNDArray()
        except PySpin.SpinnakerException as ex:
            logger.error(f'Error reading frame: {ex}')
            return False, None
        if img.IsIncomplete():
            status = img.GetImageStatus()
            error_msg = img.GetImageStatusDescription(status)
            logger.warning(f'Incomplete Image: {error_msg}')
            return False, None

    def getFeature(self, key: str) -> Value:
        if hasattr(self.device, key):
            feature = getattr(self.device, key)
            if PySpin.IsAvailable(feature) and PySpin.IsReadable(feature):
                return feature.GetValue()
        return None

    def setFeature(self, key: str, value: Value) -> bool:
        if hasattr(self.device, key):
            feature = getattr(self.device, key)
            if PySpin.IsAvailable(feature) and PySpin.IsReadable(feature):
                feature.SetValue(value)
                return True
        return False

    @pyqtProperty(int)
    def width(self) -> int:
        return self.getFeature('Width')

    @width.setter
    def width(self, value: int) -> None:
        if self.setFeature('Width', value):
            self.shapeChanged.emit(self.shape)

    @pyqtProperty(int)
    def height(self) -> int:
       return self.getFeature('Height')

    @height.setter
    def height(self, value: int) -> None:
        if self.setFeature('Height', value):
            self.shapeChanged.emit(self.shape)

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

    def _refineProperties(self) -> None:
        for p in self.properties():
            if getattr(self, p) is None:
                self._properties.remove(p)

    def setDefaults(self) -> None:
        # enable access to controls
        self.acquisitionframerateenable = True
        self.blacklevelselector = 'All'
        self.gammaenable = True
        self.gamma = 1.
        self.sharpeningenable = False
        # start acquisition
        self.acquisitionmode = 'Continuous'
        self.autoexposurecontrolpriority = 'Gain'
        self.exposureauto = 'Off'
        self.exposuremode = 'Timed'
        self.exposuretimemode = 'Common'
        self.gainauto = 'Off'
        self.sharpeningauto = 'Off'


def main() -> None:
    from pprint import pprint

    logger.setLevel(logging.ERROR)
    camera = QSpinnakerCamera()
    print(camera.cameraname)
    print(f'Serial number: {camera.deviceserialnumber}')
    print('Settings:')
    pprint(camera.settings())
    camera.close()


if __name__ == '__main__':
    main()
