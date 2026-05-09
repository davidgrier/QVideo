'''Shared type aliases used across QVideo.'''
from typing import TypeAlias
from numpy.typing import NDArray
import numpy as np

Image: TypeAlias = NDArray[np.uint8]

__all__ = ['Image']
