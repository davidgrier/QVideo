from QVideo.lib import QVideoCamera
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

    #
    # private methods for handling interactions with GenICam
    #
    def _add_property(self, fname, stop=False):
        def getter(self):
            return self._get_feature(fname)

        @QVideoCamera.protected
        def setter(self, value, stop=stop):
            self._set_feature(fname, value)

        dtype = self._feature_type(fname)
        return pyqtProperty(dtype, getter, setter)

    def _properties(self):

    _fmap = {PySpin.intfICategory: PySpin.CCategoryPtr,
             PySpin.intfIString: PySpin.CStringPtr,
             PySpin.intfIInteger: PySpin.CIntegerPtr,
             PySpin.intfIFloat: PySpin.CFloatPtr,
             PySpin.intfIBoolean: PySpin.CBooleanPtr,
             PySpin.intfICommand: PySpin.CCommandPtr,
             PySpin.intfIEnumeration: PySpin.CEnumerationPtr}

    _tmap = {PySpin.intfICategory: str,
             PySpin.intfIString: str,
             PySpin.intfIInteger: int,
             PySpin.intfIFloat: float,
             PySpin.intfIBoolean: bool,
             PySpin.intfICommand: str,
             PySpin.intfIEnumeration: str}

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

    def _feature_type(self, fname):
        node = self._nodes.GetNode(fname)
        type = node.GetPrincipalInterfaceType()
        return self._tmap[type]

    def _get_feature(self, fname):
        value = None
        feature = self._feature(fname)
        if self._is_category(feature):
            nodes = feature.GetFeatures()
            names = [node.GetName() for node in nodes]
            value = {name: self._get_feature(name) for name in names}
        elif self._is_enum(feature) or self._is_command(feature):
            value = feature.ToString()
        elif self._is_readable(feature):
            value = feature.GetValue()
        logger.debug(f'Getting {fname}: {value}')
        return value

    def _get_features(self):
        '''Return dict of camera inodes and values'''
        return self._get_feature('Root')

    def _set_feature(self, fname, value):
        logger.debug(f'Setting {fname}: {value}')
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

    def _is_readwrite(self, feature):
        return self._is_readable(feature) and self._is_writable(feature)

    def _is_readonly(self, feature):
        return self._is_readable(feature) and not self._is_writable(feature)

    def _is_writeonly(self, feature):
        return self._is_writable(feature) and not self._is_readable(feature)
    
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

    def transport_info(self):
        '''Return dict of Transport Layer Device inodes and values'''
        nodemap = self.device.GetTLDeviceNodeMap()  # Transport layer
        try:
            info = PySpin.CCategoryPtr(nodemap.GetNode('DeviceInformation'))
            if self._is_readable(info):
                features = info.GetFeatures()
                for feature in features:
                    this = PySpin.CValuePtr(feature)
                    logger.info(f'{this.GetName()}: {this.ToString()}')
                else:
                    logger.warning('Device control information not available')
        except PySpin.SpinnakerException as ex:
            logger.warning('{}'.format(ex))


def main():
    import json

    cam = QSpinnakerCamera()
    print(json.dumps(cam.camera_info(), indent=4, sort_keys=True))
    cam.close()
    del cam


if __name__ == '__main__':
    main()
