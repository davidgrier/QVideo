from importlib.metadata import version, PackageNotFoundError
from QVideo.lib._camera import Camera

try:
    __version__ = version('QVideo')
except PackageNotFoundError:  # package not installed (e.g. bare source checkout)
    __version__ = 'unknown'

__all__ = ['Camera', '__version__']
