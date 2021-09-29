from QVideo.lib import QVideoCamera
import PySpin
from PyQt5.QtCore import (pyqtSignal, pyqtProperty, pyqtSlot)
import logging

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

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

    propertyChanged = pyqtSignal(str)

    def Property(name, stop=False):

        logger.debug(f'Registering {name}')

        def is_enum(feature):
            iface = feature.GetPrincipalInterfaceType()
            return iface == PySpin.intfIEnumeration

        def getter(inst):
            logger.debug(f'Getting {name}')
            try:
                feature = getattr(inst.device, name)
                if not PySpin.IsReadable(feature):
                    logger.warning(f'{name} is not readable')
                    return None
                if is_enum(feature):
                    return feature.ToString()
                else:
                    return feature.GetValue()
            except PySpin.SpinnakerException as ex:
                logger.error(f'Error getting {name}: {ex}')

        @QVideoCamera.protected
        def setter(inst, value, stop=stop):
            logger.debug(f'Setting {name}: {value}')
            try:
                restart = stop and inst._running
                if restart:
                    inst.endAcquisition()
                feature = getattr(inst.device, name)
                if not PySpin.IsWritable(feature):
                    logger.warning(f'{name} is not writable')
                    return
                if is_enum(feature):
                    feature.FromString(value)
                else:
                    feature.SetValue(value)
                if restart:
                    inst.beginAcquisition()
                inst.propertyChanged.emit(name)
            except PySpin.SpinnakerException as ex:
                logger.error(f'Error setting {name}: {ex}')

        # FIXME: Get correct data type for properties
        return pyqtProperty(object, getter, setter)

    acquisitionframecount = Property('AcquisitionFrameCount')
    acquisitionframerate = Property('AcquisitionFrameRate')
    acquisitionframerateenable = Property('AcquisitionFrameRateEnable')
    acquisitionmode = Property('AcquisitionMode')
    autoexposurecontrolpriority = Property('AutoExposureControlPriority')
    blacklevel = Property('BlackLevel')
    blacklevelenable = Property('BlackLevelEnable')
    blacklevelselector = Property('BlackLevelSelector')
    devicevendorname = Property('DeviceVendorName')
    devicemodelname = Property('DeviceModelName')
    exposureauto = Property('ExposureAuto')
    exposuremode = Property('ExposureMode')
    exposuretime = Property('ExposureTime')
    exposuretimemode = Property('ExposureTimeMode')
    gain = Property('Gain')
    gainauto = Property('GainAuto')
    gamma = Property('Gamma')
    gammaenable = Property('GammaEnable')
    height = Property('Height', stop=True)
    offsetx = Property('OffsetX', stop=True)
    offsety = Property('OffsetY', stop=True)
    pixelformat = Property('PixelFormat', stop=True)
    reversex = Property('ReverseX', stop=True)
    reversey = Property('ReverseY', stop=True)
    sharpening = Property('Sharpening', stop=True)
    sharpeningauto = Property('SharpeningAuto')
    sharpeningenable = Property('SharpeningEnable')
    sharpeningthreshold = Property('SharpeningThreshold')
    width = Property('Width', stop=True)

    flipped = Property('ReverseY', stop=True)
    mirrored = Property('ReverseX', stop=True)

    def Trigger(name):
        @pyqtSlot(bool)
        def slot(inst, state):
            feature = getattr(inst.device, name)
            if PySpin.IsWritable(feature):
                feature.FromString('Once')
            else:
                logger.warning(f'Could not trigger {name}')
        return slot

    autoexposure = Trigger('ExposureAuto')
    autogain = Trigger('GainAuto')
    autosharpening = Trigger('SharpeningAuto')

    def __init__(self, *args,
                 cameraID=0,
                 mirrored=True,
                 flipped=False,
                 gray=True,
                 **kwargs):
        super().__init__(*args, **kwargs)

        self.open(cameraID)
        self._test_color()

        # enable access to controls
        self.acquisitionframerateenable = True
        self.blacklevelselector = 'All'
        self.gammaenable = True
        self.sharpeningenable = False

        # start acquisition
        self.acquisitionmode = 'Continuous'
        # self.autoexposurecontrolpriority = 'Gain'
        self.exposureauto = 'Off'
        self.exposuremode = 'Timed'
        # self.exposuretimemode = 'Common'
        self.gainauto = 'Off'
        # self.sharpeningauto = 'Off'

        self.gray = gray
        self.flipped = flipped
        self.mirrored = mirrored

        self.beginAcquisition()
        _, frame = self.read()

    def open(self, index=0):
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

    def close(self):
        '''Stop acquisition, close camera and release Spinnaker'''
        logger.debug('Cleaning up')
        self.endAcquisition()
        self.device.DeInit()
        del self.device
        self._devices.Clear()
        self._system.ReleaseInstance()
        logger.debug('Camera closed')

    def beginAcquisition(self):
        '''Start image acquisition'''
        if not self._running:
            logger.debug('Beginning acquisition')
            self._running = True
            self.device.BeginAcquisition()
            logger.debug('Acquisition started')

    def endAcquisition(self):
        '''Stop image acquisition'''
        if self._running:
            logger.debug('Ending acquisition')
            self.device.EndAcquisition()
            self._running = False
            logger.debug('Acquisition ended')

    def read(self):
        '''The whole point of the thing: Gimme da piccy'''
        try:
            img = self.device.GetNextImage()
        except PySpin.SpinnakerException:
            return False, None
        if img.IsIncomplete():
            status = img.GetImageStatus()
            error_msg = img.GetImageStatusDescription(status)
            logger.warning(f'Incomplete Image: {error_msg}')
            return False, None
        frame = img.GetNDArray()
        return True, frame

    def is_available(self, name):
        feature = getattr(self.device, name)
        return PySpin.IsAvailable(feature)

    def is_readable(self, name):
        feature = getattr(self.device, name)
        return PySpin.IsReadable(feature)

    def is_writable(self, name):
        feature = getattr(self.device, name)
        return PySpin.IsWritable(feature)

    @pyqtProperty(str)
    def cameraname(self):
        return f'{self.devicevendorname} {self.devicemodelname}'

    @pyqtProperty(bool)
    def gray(self):
        return self.pixelformat == 'Mono8'

    @gray.setter
    def gray(self, gray):
        logger.debug(f'Setting Gray: {gray}')
        self.pixelformat = 'Mono8' if gray else 'RGB8Packed'

    @pyqtProperty(str)
    def version(self):
        v = self._system.GetLibraryVersion()
        s = f'{v.major}.{v.minor}.{v.type}.{v.build}'
        logger.debug(f'PySpin version: {s}')
        return s

    def colorCapable(self):
        return self._color_capable

    def _test_color(self):
        if self.pixelformat == 'RGB8Packed':
            self._color_capable = True
        else:
            try:
                self.pixelformat = 'RGB8Packed'
                self._color_capable = True
            except PySpin.SpinnakerException:
                self._color_capable = False
            self.pixelformat = 'Mono8'


def main():
    cam = QSpinnakerCamera()
    print(cam.properties())
    print(cam.methods())
    cam.close()
    del cam


if __name__ == '__main__':
    main()
