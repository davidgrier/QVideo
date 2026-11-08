'''Save an image to a file, with a default name and a report.'''
from qtpy import QtCore, QtWidgets
from QVideo.lib.videotypes import Image
from QVideo.lib.imageops import save_image
from pathlib import Path
import datetime
import logging


logger = logging.getLogger(__name__)

__all__ = ['QImageSaver']


class QImageSaver(QtCore.QObject):

    '''Save images that an application passes in, and say what happened.

    The image is an argument, so any array can be saved: a frame from the
    screen, the pattern on a spatial light modulator, or the result of an
    analysis.  :class:`~QVideo.lib.QSnapshot.QSnapshot` uses one to save the
    frames that it caches.

    Parameters
    ----------
    parent : QObject, optional
        Parent.  If it is a widget, it is the parent of the file dialog.
    directory : str or Path, optional
        Where files with a generated name go.  Default: the current
        directory.
    prefix : str
        Start of a generated name.  Default: ``'image'``.
    extension : str
        End of a generated name; it sets the format.  Default: ``'.png'``.
    title : str
        Title of the file dialog.  Default: ``'Save Image'``.

    Signals
    -------
    message(str)
        What happened to each image: ``Saved <path>`` or
        ``Could not save <path>: <reason>``.  Connect it to the status bar.

    Notes
    -----
    A generated name is ``<prefix>_<YYYYMMDD>_<HHMMSS><extension>``, and an
    existing file is never overwritten by it: ``_1``, ``_2`` and so on are
    added.  A name that the caller (or the user in the dialog) gives is
    used as it is.
    '''

    message = QtCore.Signal(str)

    def __init__(self, parent: QtCore.QObject | None = None,
                 directory: str | Path | None = None,
                 prefix: str = 'image',
                 extension: str = '.png',
                 title: str = 'Save Image') -> None:
        super().__init__(parent)
        self.directory = Path(directory) if directory else Path.cwd()
        self.prefix = prefix
        self.extension = extension
        self.title = title

    def defaultPath(self, prefix: str | None = None) -> str:
        '''Return a timestamped path that does not exist yet.

        *prefix* replaces :attr:`prefix` for this name.
        '''
        now = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        stem = f'{prefix or self.prefix}_{now}'
        path = self.directory / f'{stem}{self.extension}'
        count = 0
        while path.exists():
            count += 1
            path = self.directory / f'{stem}_{count}{self.extension}'
        return str(path)

    def save(self, image: Image, filename: str | Path | None = None,
             ask: bool = False,
             levels: tuple[float, float] | None = None,
             prefix: str | None = None) -> str | None:
        '''Save *image* and report the outcome.

        Parameters
        ----------
        image : Image
            See :func:`~QVideo.lib.imageops.save_image`.
        filename : str or Path, optional
            Where to save it.  Default: a generated name, which is also the
            suggestion when *ask* is set.
        ask : bool
            Open a file dialog first.  Default: ``False``.
        levels : tuple[float, float], optional
            Black and white of a ``uint16`` image.
        prefix : str, optional
            Start of the generated name, instead of :attr:`prefix`.

        Returns
        -------
        str or None
            The path that was written, or ``None`` if the user cancelled
            or the file could not be saved.
        '''
        path = str(filename) if filename else self.defaultPath(prefix)
        if ask:
            parent = self.parent()
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                parent if isinstance(parent, QtWidgets.QWidget) else None,
                self.title, path,
                'PNG Images (*.png);;TIFF Images (*.tiff);;'
                'JPEG Images (*.jpg)')
            if not path:
                return None
        try:
            save_image(image, path, levels)
        except (ValueError, OSError) as error:
            logger.warning(f'Could not save {path!r}: {error}')
            self.message.emit(f'Could not save {path}: {error}')
            return None
        logger.info(f'Saved {path!r}')
        self.message.emit(f'Saved {path}')
        return path
