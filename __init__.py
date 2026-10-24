from importlib.metadata import version, PackageNotFoundError
try:
    import qtpy  # noqa: F401  (selects the Qt binding)
except RuntimeError as error:
    raise ImportError(
        'QVideo needs a Qt binding.  Install one with '
        'pip install "QVideo[pyqt6]" (recommended) or '
        'pip install "QVideo[pyqt5]"') from error
from QVideo.lib._camera import Camera

try:
    __version__ = version('QVideo')
except PackageNotFoundError:  # package not installed (e.g. bare source checkout)
    __version__ = 'unknown'

__all__ = ['Camera', '__version__']
