from QVideoCamera import QVideoCamera
import numpy as np


class QNoiseSource(QVideoCamera):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.width = 640
        self.height = 480
        self.shape = (self.height, self.width)
        self.rng = np.random.default_rng()

    def read(self):
        image = self.rng.integers(0, 255, self.shape, np.uint8)
        return True, image
