from QVideo.lib import QVideoCamera
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


class QSpinnakerCamera(QVideoCamera):

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

        @QVideoCamera.protected
        def setter(inst, value: Value) -> None:
            logger.debug(f'Setting {name}: {value}')
            try:
                restart = stop and inst._running
                if restart:
                    inst.endAcquisition()
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
                if restart:
                    inst.beginAcquisition()
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

        self.open(cameraID)
        self._test_color()
        self._update_properties()
        self.initial_settings()
        self.flipped = flipped
        self.mirrored = mirrored
        self.gray = gray
        self.beginAcquisition()
        _, frame = self.read()

    def initial_settings(self) -> None:
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


    def open(self, index: int = 0) -> None:
        '''
        Initialize Spinnaker and open specified camera

        Keywords
        --------
        index : int
            Index of camera to open. Default: 0
        '''
        # Initialize Spinnaker and get list of cameras
        self._system = PySpin.System.GetInstance()
        self._devices = self._system.GetCameras()
        ncameras = self._devices.GetSize()
        if ncameras < 1:
            self._devices.Clear()
            self._system.ReleaseInstance()
            raise IndexError('No Spinnaker cameras found')
        logger.debug(f'{ncameras} Spinnaker cameras found')

        # Initialize selected camera
        logger.debug(f'Initializing camera {index}')
        self.device = self._devices[index]
        self.device.Init()
        self._running = False
        logger.debug(f'Camera {index} open')

    def close(self) -> None:
        '''Stop acquisition, close camera and release Spinnaker'''
        logger.debug('Cleaning up')
        if self.device.IsStreaming():
            self.endAcquisition()
        self.device.DeInit()
        del self.device
        self._devices.Clear()
        if not self._system.IsInUse():
            self._system.ReleaseInstance()
            del self._system
        logger.debug('Camera closed')

    def beginAcquisition(self) -> None:
        '''Start image acquisition'''
        if not self._running:
            logger.debug('Beginning acquisition')
            self._running = True
            self.device.BeginAcquisition()
            logger.debug('Acquisition started')

    def endAcquisition(self) -> None:
        '''Stop image acquisition'''
        if self._running:
            logger.debug('Ending acquisition')
            self.device.EndAcquisition()
            self._running = False
            logger.debug('Acquisition ended')

    def read(self) -> tuple[bool, 'np.ndarray']:
        '''The whole point of the thing: Gimme da piccy'''
        try:
            img = self.device.GetNextImage()
        except PySpin.SpinnakerException as ex:
            logger.error(f'Error reading frame: {ex}')
            return False, None
        if img.IsIncomplete():
            status = img.GetImageStatus()
            error_msg = img.GetImageStatusDescription(status)
            logger.warning(f'Incomplete Image: {error_msg}')
            return False, None
        frame = img.GetNDArray()
        return True, frame

    @pyqtProperty(int)
    def width(self) -> int:
        feature = getattr(self.device, 'Width')
        if PySpin.IsAvailable(feature) and PySpin.IsReadable(feature):
            return feature.GetValue()
        return -1

    @width.setter
    def width(self, value: int) -> None:
        feature = getattr(self.device, 'Width')
        if PySpin.IsAvailable(feature) and PySpin.IsReadable(feature):
            feature.SetValue(value)
            self.shapeChanged.emit(self.shape)

    @pyqtProperty(int)
    def height(self) -> int:
        feature = getattr(self.device, 'Height')
        if PySpin.IsAvailable(feature) and PySpin.IsReadable(feature):
            return feature.GetValue()
        return -1

    @height.setter
    def height(self, value: int) -> None:
        feature = getattr(self.device, 'Width')
        if PySpin.IsAvailable(feature) and PySpin.IsReadable(feature):
            feature.SetValue(value)
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

    def _test_color(self) -> None:
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

    def _update_properties(self) -> None:
        for p in self.properties():
            if getattr(self, p) is None:
                self._properties.remove(p)


def main() -> None:
    from pprint import pprint

    logger.setLevel(logging.ERROR)
    cam = QSpinnakerCamera()
    print(cam.cameraname)
    print(f'Serial number: {cam.deviceserialnumber}')
    print('Settings:')
    pprint(cam.settings)
    cam.close()
    del cam


if __name__ == '__main__':
    main()
