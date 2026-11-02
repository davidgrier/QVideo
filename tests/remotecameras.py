'''Cameras that fail the way a good camera does not, for the tests of
:class:`QVideo.lib.QRemoteCamera`.

A worker opens them by name: ``'QVideo.tests.remotecameras:FailingCamera'``.
This module creates no ``QApplication``, because the worker has none.
'''
import os

import numpy as np

from QVideo.cameras.Noise import QNoiseCamera

__all__ = 'FailingCamera FloatCamera StatesCamera'.split()


class FailingCamera(QNoiseCamera):

    '''A camera whose every read fails.'''

    def read(self):
        raise RuntimeError('no sensor')


class FloatCamera(QNoiseCamera):

    '''A camera that returns frames that the ring cannot hold.'''

    def read(self):
        return True, np.zeros((480, 640))


class StatesCamera(QNoiseCamera):

    '''A camera that answers for nodes the way a GenICam camera does.'''

    def states(self, names):
        return {name: dict(writable=True, kind='int', value=os.getpid())
                for name in names}
