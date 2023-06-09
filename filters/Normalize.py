from QVideo.filters.Median import Median
from QVideo.filters.MoMedian import MoMedian
import numpy as np


def Normalize_Factory(base_class):

    class Normalize(base_class):

        '''Normalize image by running-median background estimate

        Inherits
        --------
        QVideo.filters.Median

        Properties
        ----------
        scale: bool
            True: scale normalized image to mean and cast to uint8
            False: return floating-point result
            Default: True
        mean: float
            Mean value for scale. Default: 100.
        darkcount: uint8
            darkcount to subtract from each frame before normalizing
            Default: 0

        Methods
        -------
        add(data: np.ndarray): None
            Incorporates new image data into the running median
            estimate for the background.
        get(): np.ndarray
            Returns normalized image
        '''

        def __init__(self, *args,
                     scale: bool = True,
                     mean: float = 100.,
                     darkcount: np.uint8 = 0,
                     **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self.scale = scale
            self.mean = mean
            self.darkcount = darkcount

        def add(self, data: np.ndarray) -> None:
            '''Incorporates new data into background estimate'''
            data -= self.darkcount
            super().add(data)
            self._fg = data

        def get(self) -> np.ndarray:
            '''Returns background-corrected image'''
            bg = super().get()
            result = np.divide(self._fg, bg, where=(bg != 0))
            if self.scale:
                result = (self.mean * result).astype(np.uint8)
            return result

    return Normalize


Normalize = Normalize_Factory(Median)
SmoothNormalize = Normalize_Factory(MoMedian)
