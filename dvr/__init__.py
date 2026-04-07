from .QDVRWidget import QDVRWidget
from .QOpenCVWriter import QOpenCVWriter
from .QOpenCVReader import QOpenCVReader, QOpenCVSource
from .QHDF5Writer import QHDF5Writer
from .QHDF5Reader import QHDF5Reader, QHDF5Source

__all__ = [
    'QDVRWidget',
    'QOpenCVWriter',
    'QOpenCVReader', 'QOpenCVSource',
]

try:
    import h5py as _h5py
    __all__ += ['QHDF5Writer', 'QHDF5Reader', 'QHDF5Source']
except (ImportError, ModuleNotFoundError):
    pass
