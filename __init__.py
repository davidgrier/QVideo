from importlib.metadata import version, PackageNotFoundError
from QVideo.lib import QVideoScreen

try:
    __version__ = version('QVideo')
except PackageNotFoundError:  # package not installed (e.g. bare source checkout)
    __version__ = 'unknown'

__all__ = ['QVideoScreen', '__version__']
