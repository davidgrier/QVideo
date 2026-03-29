'''Shared type aliases used across QVideo.'''
from numpy.typing import NDArray
import numpy as np

Image = NDArray[np.uint8]

__all__ = ['Image']
