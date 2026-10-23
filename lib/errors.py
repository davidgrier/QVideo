'''Exceptions raised when a camera cannot be opened.'''


__all__ = ['QCameraError', 'QDriverError', 'QDeviceError']


class QCameraError(RuntimeError):
    '''Base class for failures to open a camera.

    The message is intended for end users: it says what is wrong and,
    where possible, what to do about it.
    '''


class QDriverError(QCameraError):
    '''The software needed to talk to a camera is missing or unusable.

    Examples are an uninstalled Python package, an unset
    ``GENICAM_GENTL64_PATH`` or a GenTL producer that cannot be loaded.
    '''


class QDeviceError(QCameraError):
    '''The driver works, but the requested camera could not be opened.'''
