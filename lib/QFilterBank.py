'''Composable pipeline of VideoFilter stages between a source and a display.'''
import logging
from typing import Iterator

from pyqtgraph.Qt import QtWidgets
from QVideo.lib.QVideoFilter import QVideoFilter
from QVideo.lib.videotypes import Image
import QVideo.filters as videofilters


__all__ = ['QFilterBank']

logger = logging.getLogger(__name__)


class QFilterBank(QtWidgets.QGroupBox):

    '''A vertical stack of :class:`~QVideo.lib.VideoFilter.QVideoFilter` widgets.

    Applies a sequence of video filters to each frame in order.
    Filters are added and removed at runtime via :meth:`register` and
    :meth:`deregister`, and may also be looked up by name from the
    :mod:`QVideo.filters` package using :meth:`registerByName`.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.
    '''

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__('Display Filters', parent)
        self._filters = []
        self._setupUi()

    def _setupUi(self) -> None:
        self._layout = QtWidgets.QVBoxLayout(self)

    def __iter__(self) -> Iterator[QVideoFilter]:
        return iter(self._filters)

    @property
    def filters(self) -> list[QVideoFilter]:
        '''Read-only view of the registered filters.'''
        return list(self._filters)

    def __call__(self, image: Image) -> Image:
        '''Apply all registered filters to *image* in order.

        Parameters
        ----------
        image : Image
            Input frame.

        Returns
        -------
        Image
            Frame after all enabled filters have been applied.
        '''
        for video_filter in self:
            image = video_filter(image)
        return image

    def register(self, video_filter: QVideoFilter) -> None:
        '''Add a filter to the end of the pipeline.

        Parameters
        ----------
        video_filter : QVideoFilter
            Filter widget to add.

        Raises
        ------
        TypeError
            If *video_filter* is not a :class:`~QVideo.lib.VideoFilter.QVideoFilter`.
        '''
        if not isinstance(video_filter, QVideoFilter):
            raise TypeError('expected QVideoFilter, '
                            f'got {type(video_filter).__name__}')
        self._filters.append(video_filter)
        self._layout.addWidget(video_filter)

    def deregister(self, video_filter: QVideoFilter) -> None:
        '''Remove a filter from the pipeline.

        Parameters
        ----------
        video_filter : QVideoFilter
            Filter widget to remove.

        Raises
        ------
        ValueError
            If *video_filter* is not currently registered.
        '''
        self._filters.remove(video_filter)
        self._layout.removeWidget(video_filter)
        video_filter.setParent(None)

    def registerByName(self, name: str) -> None:
        '''Instantiate a filter by class name and add it to the pipeline.

        Looks up *name* in the :mod:`QVideo.filters` package and
        registers an instance if found.

        Parameters
        ----------
        name : str
            Name of a :class:`~QVideo.lib.VideoFilter.QVideoFilter`
            subclass exported by :mod:`QVideo.filters`.

        Raises
        ------
        ValueError
            If *name* is not found in :mod:`QVideo.filters` or does not
            refer to a :class:`~QVideo.lib.VideoFilter.QVideoFilter`
            subclass.
        '''
        cls = getattr(videofilters, name, None)
        if cls is None or not (isinstance(cls, type) and
                               issubclass(cls, QVideoFilter)):
            raise ValueError(f'{name!r} is not a known filter')
        try:
            self.register(cls())
        except Exception as e:
            logger.warning(f'Failed to instantiate filter {name!r}: {e}')
