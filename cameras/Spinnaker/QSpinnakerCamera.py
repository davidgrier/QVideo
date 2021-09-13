from QVideo.lib import QVideoCamera
import PySpin
from PyQt5.QtCore import pyqtProperty
import logging

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

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

    def Property(name, stop=False):

        def getter(self):
            logger.debug(f'Getting {name}')
            feature = getattr(self.device, name)
            if not PySpin.IsReadable(feature):
                logger.warning(f'{name} is not readable')
                return None
            iface = feature.GetPrincipalInterfaceType()
            is_enum = iface == PySpin.intfIEnumeration
            return feature.ToString() if is_enum else feature.GetValue()

        @QVideoCamera.protected
        def setter(self, value, stop=stop):
            logger.debug(f'Setting {name}: {value}')
            restart = stop and self._running
            if restart:
                self.endAcquisition()
            feature = getattr(self.device, name)
            if not PySpin.IsWritable(feature):
                logger.warning(f'{name} is not writable')
                return
            iface = feature.GetPrincipalInterfaceType()
            is_enum = iface == PySpin.intfIEnumeration
            fset = feature.FromString if is_enum else feature.SetValue
            fset(value)
            if restart:
                self.beginAcquisition()

        return pyqtProperty(object, getter, setter)

    acquisitionframecount = Property('AcquisitionFrameCout')
    acquisitionframerate = Property('AcquisitionFrameRate')
    acquisitionframerateenable = Property('AcquisitionFrameRateEnable')
    acquisitionmode = Property('AcquisitionMode')
    blacklevel = Property('BlackLevel', int)
    blacklevelenable = Property('BlackLevelEnable')
    blacklevelselector = Property('BlackLevelSelector')
    devicevendorname = Property('DeviceVendorName')
    devicemodelname = Property('DeviceModelName')
    exposureauto = Property('ExposureAuto')
    exposuremode = Property('ExposureMode')
    exposuretime = Property('ExposureTime')
    gain = Property('Gain')
    gainauto = Property('GainAuto')
    gamma = Property('Gamma')
    gammaenable = Property('GammaEnable')
    height = Property('Height', stop=True)
    pixelformat = Property('PixelFormat')
    reversex = Property('ReverseX', stop=True)
    reversey = Property('ReverseY', stop=True)
    sharpening = Property('Sharpening')
    sharpeningauto = Property('SharpeningAuto')
    sharpeningenable = Property('SharpeningEnable')
    sharpeningthreshold = Property('SharpeningThreshold')
    width = Property('Width', stop=True)

    def GetRange(name):
        def getter(self):
            feature = getattr(self.device, name)
            if not PySpin.IsAvailable(feature):
                return None
            return (feature.GetMin(), feature.GetMax())
        return pyqtProperty(object, getter)

    acquisitionframeraterange = GetRange('AcquisitionFrameRate')
    blacklevelrange = GetRange('BlackLevel')
    exposuretimerange = GetRange('ExposureTime')
    gainrange = GetRange('Gain')
    gammarange = GetRange('Gamma')

    def __init__(self, *args,
                 cameraID=0,
                 mirrored=False,
                 flipped=False,
                 gray=True,
                 **kwargs):
        super().__init__(*args, **kwargs)

        self.open(cameraID)

        # enable access to controls
        self.acquisitionframerateenable = True
        self.blacklevelselector = 'All'
        self.gammaenable = True
        self.sharpeningenable = False

        # start acquisition
        self.acquisitionmode = 'Continuous'
        self.exposureauto = 'Off'
        self.exposuremode = 'Timed'
        self.gainauto = 'Off'
        self.sharpeningauto = 'Off'

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
        # implement flipped and mirrored if necessary
        return True, frame

    def is_available(self, name):
        feature = getattr(self.device, name)
        return PySpin.IsAvailable(feature)

    @pyqtProperty(str)
    def cameraname(self):
        return f'{self.devicevendorname} {self.device.modelname}'

    @pyqtProperty(bool)
    def flipped(self):
        if self.is_available('ReverseX'):
            return self.reversex
        else:
            return self._flipped

    @flipped.setter
    def flipped(self, value):
        if self.is_available('ReverseX'):
            self.reversex = value
            self._flipped = False
        else:
            self._flipped = value

    @pyqtProperty(bool)
    def gray(self):
        return self.pixelformat == 'Mono8'

    @QVideoCamera.protected
    @gray.setter
    def gray(self, gray):
        logger.debug(f'Setting Gray: {gray}')
        self.pixelformat = 'Mono8' if gray else 'RGB8Packed'

    @pyqtProperty(bool)
    def mirrored(self):
        if self.is_available('ReverseY'):
            return self.reversey
        else:
            return self._mirrored

    @mirrored.setter
    def mirrored(self, value):
        if self.is_available('ReverseY'):
            self.reversey = value
            self.mirrored = False
        else:
            self._mirrored = value

    @pyqtProperty(str)
    def version(self):
        v = self._system.GetLibraryVersion()
        s = f'{v.major}.{v.minor}.{v.type}.{v.build}'
        logger.debug(f'PySpin version: {s}')
        return s

    def autoexposure(self):
        self.exposureauto = 'Once'

    def autogain(self):
        self.gainauto = 'Once'


def main():
    import json

    cam = QSpinnakerCamera()
    #    print(json.dumps(cam.camera_info(), indent=4, sort_keys=True))
    print(dir(cam.device))
    cam.close()
    del cam


if __name__ == '__main__':
    main()
