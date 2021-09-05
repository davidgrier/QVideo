from QVideoCamera import QVideoCamera
import PySpin
from PyQt5.QtCore import pyqtProperty
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

    '''Abstraction of FLiR camera for PyFab/Jansen

    ...

    Properties
    ==========
    device: PySpin.CameraPtr
        camera device in Spinnaker system
    cameraname : str
        Vendor and camera model

    Acquisition Control
    -------------------
    acquisitionmode : str
        Mode for acquiring frames:
        'Continuous': acquire frames continuously (Default)
        'MultiFrame': acquire specified number of frames
        'SingleFrame': acquire one image before stopping
    acquisitionframecount : int
        Number of frames to acquire with MultiFrame
    exposuremode : str
        Mode for setting single-frame exposure:
        'Timed': Fixed exposure time (Default)
        'TriggerWidth': Determined by external trigger
    exposuretime : float
        Exposure time in microseconds when exposuremode is 'Timed'
    exposuretimerange : (float, float)
        Range of exposure times in microseconds
    exposureauto: str
        Automatic exposure mode:
        'Off': Do not adjust exposure time (Default)
        'Once': Optimize exposure time, then return to 'Off'
        'Continuous': Optimize exposure time
    framerate : float
        Acquisition frame rate in Hertz
    framerateenable : bool
        Manually control framerate
    frameraterange : (float, float)
        Range of frame rates in Hertz
    framerateauto: str
        Automatic frame rate mode:
        'Off': Do not optimize frame rate (Default)
        'Continuous': Optimize frame rate

    NOTE: Trigger Commands are not yet implemented

    Analog Control
    --------------
    gain : float
        Amplification of video signal in dB
    gainrange : (float, float)
        Range of gain values in dB
    gainauto: 
        Enable automatic control of gain
        'Off': Do not adjust gain (Default)
        'Once': Optimize gain, then return to 'Off'
        'Continuous': Optimize gain
    blacklevel : int
        Offset of video signal in camera-specific units
    blacklevelrange : (int, int)
        Range of black level values
    gamma : float
        Gamma correction of pixel intensity
    gammarange : (float, float)
        Range of gamma values
    gammaenable : bool
        Enable gamma correction
        Default: True
    sharpening : float
        Amount of sharpening to apply to image
        Default: 2.
    sharpeningrange : (float, float)
        Range of sharpening values
    sharpeningenable : bool
        Enable image sharpening
        Default: False
    sharpeningthreshold : float
        Only sharpen regions with intensity changes greater than threshold
    sharpeningthresholdrange : (float, float)
        Range of sharpening threshold values

    Image Format Control
    --------------------
    flipped : bool
        Vertically flip image
    mirrored : bool
        Horizontally flip image
    gray: bool
        True: read() returns single-channel (grayscale) image
        False: read() returns RGB8Packed three-channel image

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

    def Property(pstr, dtype=float, stop=False):
        def getter(self):
            return self._get_feature(pstr)

        @QVideoCamera.protected
        def setter(self, value, stop=stop):
            if stop and self._running:
                self.endAcquisition()
                self._set_feature(pstr, value)
                self.beginAcquisition()
            else:
                self._set_feature(pstr, value)
        return pyqtProperty(dtype, getter, setter)

    def GetRange(pstr):
        @pyqtProperty(object)
        def prop(self):
            return self._feature_range(pstr)
        return prop

    acquisitionframecount       = Property('AcquisitionFrameCount')
    acquisitionframerate        = Property('AcquisitionFrameRate')
    acquisitionmode             = Property('AcquisitionMode')
    blacklevel                  = Property('BlackLevel')
    blacklevelrange             = GetRange('BlackLevel')
    blacklevelauto              = Property('BlackLevelAuto')
    blacklevelenable            = Property('BlackLevelEnabled')
    exposureauto                = Property('ExposureAuto')
    exposuremode                = Property('ExposureMode')
    exposuretime                = Property('ExposureTime', dtype=float)
    exposuretimerange           = GetRange('ExposureTime')
    # flipped                    = Property('ReverseY', stop=True)
    framerate                   = Property('AcquisitionFrameRate')
    framerateenable             = Property('AcquisitionFrameRateEnabled')
    frameraterange              = GetRange('AcquisitionFrameRate')
    gain                        = Property('Gain')
    gainauto                    = Property('GainAuto')
    gainrange                   = GetRange('Gain')
    gamma                       = Property('Gamma')
    gammaenable                 = Property('GammaEnabled')
    gammarange                  = GetRange('Gamma')
    height                      = Property('Height', stop=True)
    mirrored                    = Property('ReverseX', stop=True)
    pixelformat                 = Property('PixelFormat')
    reversex                    = Property('ReverseX', stop=True)
    # reversey                   = Property('ReverseY', stop=True)
    sharpening                  = Property('Sharpness')
    sharpeningauto              = Property('SharpnessAuto')
    sharpeningenable            = Property('SharpnessEnabled')
    sharpeningthreshold         = Property('SharpeningThreshold')
    width                       = Property('Width', stop=True)

    def __init__(self,
                 *args,
                 framerateenable=True,
                 gammaenable=True,
                 sharpeningenable=False,
                 acquisitionmode='Continuous',
                 exposureauto='Off',
                 exposuremode='Timed',
                 framerateauto='Off',
                 gainauto='Off',
                 sharpeningauto='Off',
                 gray=True,
                 flipped=False,
                 mirrored=False,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.open()

        # Enable access to controls
        self.blacklevelselector = 'All'
        self.framerateenable = framerateenable
        self.gammaenable = gammaenable
        self.sharpeningenable = sharpeningenable

        # Start acquisition
        self.acquisitionmode = acquisitionmode
        self.exposureauto = exposureauto
        self.exposuremode = exposuremode
        self.sharpeningauto = sharpeningauto
        self.framerateauto = framerateauto
        self.gainauto = gainauto

        self.gray = gray
        self.flipped = flipped
        self.mirrored = mirrored

        self.beginAcquisition()
        ready, frame = self.read()

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
        if self._devices.GetSize() < 1:
            raise IndexError('No Spinnaker cameras found')

        # Initialize selected camera and get map of nodes
        self.device = self._devices[index]
        self.device.Init()
        self._nodes = self.device.GetNodeMap()

        self._running = False

    def close(self):
        '''Stop acquisition, close camera and release Spinnaker'''
        logger.debug('Cleaning up')
        self.endAcquisition()
        self.device.DeInit()
        del self.device
        self._devices.Clear()
        self._system.ReleaseInstance()

    def beginAcquitision(self):
        '''Start image acquisition'''
        if not self._running:
            self._running = True
            self.device.BeginAcquisition()

    def endAcquisition(self):
        '''Stop image acquisition'''
        if self._running:
            self.device.EndAcquisition()
            self._running = False

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

    @pyqtProperty(str)
    def cameraname(self):
        vendor = self._get_feature('DeviceVendorName')
        model = self._get_feature('DeviceModelName')
        return f'{vendor} {model}'

    @cameraname.setter
    def cameraname(self, value):
        logger.debug(f'Attempting to set camera name: {value}')

    @pyqtProperty(bool)
    def flipped(self):
        # return bool(self._get_feature('ReverseY'))
        return self._flipped

    @flipped.setter
    def flipped(self, value):
        # self._set_feature('ReverseY', bool(value))
        self._flipped = value

    @pyqtProperty(float)
    def frameratemax(self):
        return self._feature('AcquisitionFrameRate').GetMax()

    @pyqtProperty(float)
    def frameratemin(self):
        return self._feature('AcquisitionFrameRate').GetMin()

    @pyqtProperty(bool)
    def gray(self):
        return self.pixelformat == 'Mono8'

    @gray.setter
    @QVideoCamera.protected
    def gray(self, gray):
        self.pixelformat = 'Mono8' if gray else 'RGB8Packed'

    @pyqtProperty(int)
    def heightmax(self):
        return self._get_feature('HeightMax')

    @pyqtProperty(float)
    def sharpeningrange(self):
        return (1., 8.)

    @pyqtProperty(float)
    def sharpeningthresholdrange(self):
        return (0., 0.25)

    '''
    @property
    def videomode(self):
        return self._feature('VideoMode').GetValue()

    @videomode.setter
    def videomode(self, mode):
        self.stop()
        self._feature('VideoMode').SetValue(mode)
        self.start()
    '''

    @pyqtProperty(int)
    def widthmax(self):
        return self._get_feature('WidthMax')

    def autoexposure(self):
        self.exposureauto = 'Once'

    def autogain(self):
        self.gainauto = 'Once'

    #
    # private methods for handling interactions with GenICam
    #
    _fmap = {PySpin.intfICategory: PySpin.CCategoryPtr,
             PySpin.intfIString: PySpin.CStringPtr,
             PySpin.intfIInteger: PySpin.CIntegerPtr,
             PySpin.intfIFloat: PySpin.CFloatPtr,
             PySpin.intfIBoolean: PySpin.CBooleanPtr,
             PySpin.intfICommand: PySpin.CCommandPtr,
             PySpin.intfIEnumeration: PySpin.CEnumerationPtr}

    def _feature(self, fname):
        '''Return inode for named feature'''
        feature = None
        try:
            node = self._nodes.GetNode(fname)
            type = node.GetPrincipalInterfaceType()
            feature = self._fmap[type](node)
        except Exception as ex:
            logger.warning(f'Could not access Property: {fname} {ex}')
        return feature

    def _get_feature(self, fname):
        value = None
        feature = self._feature(fname)
        if self._is_enum(feature) or self._is_command(feature):
            value = feature.ToString()
        elif self._is_category(feature):
            nodes = feature.GetFeatures()
            value = dict()
            for node in nodes:
                name = node.GetName()
                value[name] = self._get_feature(name)
        elif self._is_readable(feature):
            value = feature.GetValue()
        logger.debug(f'Getting {fname}: {value}')
        return value

    def _set_feature(self, fname, value):
        logger.debug('Setting {fname}: {value}')
        feature = self._feature(fname)
        if not self._is_writable(feature):
            logger.warning(f'Property {fname} is not writable')
            return
        try:
            if self._is_enum(feature) or self._is_command(feature):
                feature.FromString(value)
            else:
                feature.SetValue(value)
        except PySpin.SpinnakerException as ex:
            logger.warning(f'Could not set {fname}: {ex}')

    def _feature_range(self, fname):
        '''Return minimum and maximum values of named feature'''
        feature = self._feature(fname)
        try:
            range = (feature.GetMin(), feature.GetMax())
        except PySpin.SpinnakerException as ex:
            logger.warning(f'Could not get range of {fname}: {ex}')
            range = None
        return range

    def _is_readable(self, feature):
        return PySpin.IsAvailable(feature) and PySpin.IsReadable(feature)

    def _is_writable(self, feature):
        return PySpin.IsAvailable(feature) and PySpin.IsWritable(feature)

    def _is_type(self, feature, typevalue):
        return (self._is_readable(feature) and
                feature.GetPrincipalInterfaceType() == typevalue)

    def _is_category(self, feature):
        return self._is_type(feature, PySpin.intfICategory)

    def _is_enum(self, feature):
        return self._is_type(feature, PySpin.intfIEnumeration)

    def _is_command(self, feature):
        return self._is_type(feature, PySpin.intfICommand)

    #
    # Methods for introspection
    #
    def camera_info(self):
        '''Return dict of camera inodes and values'''
        return self._get_feature('Root')

    def transport_info(self):
        '''Return dict of Transport Layer Device inodes and values'''
        nodemap = self.device.GetTLDeviceNodeMap()  # Transport layer
        try:
            info = PySpin.CCategoryPtr(nodemap.GetNode('DeviceInformation'))
            if self._is_readable(info):
                features = info.GetFeatures()
                for feature in features:
                    this = PySpin.CValuePtr(feature)
                    print('{}: {}'.format(this.GetName(), this.ToString()))
                else:
                    print('Device control information not available')
        except PySpin.SpinnakerException as ex:
            logger.warning('{}'.format(ex))


if __name__ == '__main__':
    cam = QSpinnakerCamera()
    print(cam.width)
    _, img = cam.read()
    print(img.shape)
    del cam
