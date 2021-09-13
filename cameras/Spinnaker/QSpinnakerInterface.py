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


class QSpinnakerInterface(QVideoCamera):

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
                 cameraID=0,
                 **kwargs):
        super().__init__(*args, **kwargs)

        self.open(cameraID)
        self._register_properties()

        # enable access to controls
        self.framerateenable = True
        self.gammaenable = True

        # start acquisition
        self.acquisitionmode = 'Continuous'
        
        # self.width = self._property('Width', stop=True)

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

        # Initialize selected camera and get map of nodes
        logger.debug(f'Initializing camera {index}')
        self.device = self._devices[index]
        self.device.Init()
        self._nodes = self.device.GetNodeMap()
        self._running = False
        logger.debug(f'Camera {index} open')

    def _create_properties(self):
        self.acquisitionmode = self._property('AcquisitionMode')
        self.framerate = self._property('AcquisitionFrameRate')
        self.framerateenable = self._property('AcquisitionFrameRateEnable')
        self.gammaenable = self._property('GammaEnable')
        
    def version(self):
        v = self._system.GetLibraryVersion()
        s = f'{v.major}.{v.minor}.{v.type}.{v.build}'
        logger.debug(f'PySpin version: {s}')
        return s

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
        return True, img.GetNDArray()

    def _property(self, name, stop=False, notify=None):

        dtype = {PySpin.intfIBoolean: bool,
                 PySpin.intfIInteger: int,
                 PySpin.intfIFloat: float,
                 PySpin.intfIString: str,
                 PySpin.intfIEnumeration: str}
        try:
            feature = getattr(self.device, name)
        except AttributeError:
            logger.warning(f'Camera does not have feature {fname}')
            return None
        if not PySpin.IsAvailable(feature):
            logger.warning(f'{fname} is not available')
            return None
        if not PySpin.IsReadable(feature):
            logger.warning(f'{fname} is not readable')
            return None
        if not PySpin.IsWritable(feature):
            logger.warning(f'{fname} is not writable')
            return None

        iface = feature.GetPrincipalInterfaceType()
        is_enum = iface == PySpin.intfIEnumeration
        type = dtype[iface]
        logger.debug(f'{name}: {type.__name__}, {is_enum}')

        def getter(self):
            logger.debug(f'Getting {name}')
            get = feature.ToString if is_enum else feature.Getvalue
            return get()

        @QVideoCamera.protected
        def setter(self, value):
            logger.debug(f'Setting {name}')
            set = feature.FromString if is_enum else feature.SetValue
            if stop and self._running:
                self.endAcquisition()
                set(value)
                self.beginAcquisition()
            else:
                set(value)
            if notify is not None:
                notify.emit()

        return pyqtProperty(type, getter, setter)
                

def main():
    import json

    cam = QSpinnakerCamera()
    print(json.dumps(cam.camera_info(), indent=4, sort_keys=True))
    cam.close()
    del cam


if __name__ == '__main__':
    main()
