'''Cameras that fail the way a good camera does not, for the tests of
:class:`QVideo.lib.QRemoteCamera`.

A worker opens them by name: ``'QVideo.tests.remotecameras:FailingCamera'``.
This module creates no ``QApplication``, because the worker has none.
'''
import os

import numpy as np

from QVideo.cameras.Noise import QNoiseCamera
from QVideo.lib.errors import QDriverError

__all__ = ('FailingCamera FloatCamera StatesCamera ShrinkingCamera '
           'RefusingCamera').split()


class RefusingCamera(QNoiseCamera):

    '''A camera that cannot open, and says why, as one without a producer.'''

    def _initialize(self):
        raise QDriverError('no producer here')


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


class ShrinkingCamera(QNoiseCamera):

    '''A camera that makes its frames smaller on its own, after a while,
    without anyone asking.'''

    FRAMES = 30

    def read(self):
        self._frames = getattr(self, '_frames', 0) + 1
        ok, frame = super().read()
        if ok and self._frames > self.FRAMES:
            frame = np.ascontiguousarray(frame[::2, ::2])
        return ok, frame
