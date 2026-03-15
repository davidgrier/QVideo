from pyqtgraph.Qt import QtWidgets
from QVideo.lib.VideoFilter import QVideoFilter
from QVideo.lib.types import Image
import QVideo.filters as filters_pkg


__all__ = ['QFilterBank']


class QFilterBank(QtWidgets.QGroupBox):

    '''A vertical stack of :class:`~QVideo.lib.VideoFilter.QVideoFilter` widgets.

    Applies a sequence of video filters to each frame in order.
    Filters are added and removed at runtime via :meth:`register` and
    :meth:`deregister`, and may also be looked up by name from the
    :mod:`QVideo.filters` package using :meth:`registerByName`.

    Parameters
    ----------
    parent : QtWidgets.QWidget
        Parent widget.
    '''

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__('Display Filters', parent)
        self.filters = []
        self._setupUi()

    def _setupUi(self) -> None:
        self.layout = QtWidgets.QVBoxLayout(self)

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
        for video_filter in self.filters:
            image = video_filter(image)
        return image

    def register(self, video_filter: QVideoFilter) -> None:
        '''Add a filter to the end of the pipeline.

        Parameters
        ----------
        video_filter : QVideoFilter
            Filter widget to add.
        '''
        self.filters.append(video_filter)
        self.layout.addWidget(video_filter)

    def deregister(self, video_filter: QVideoFilter) -> None:
        '''Remove a filter from the pipeline.

        Parameters
        ----------
        video_filter : QVideoFilter
            Filter widget to remove.
        '''
        self.filters.remove(video_filter)
        self.layout.removeWidget(video_filter)
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
            If *name* is not found in :mod:`QVideo.filters`.
        '''
        cls = getattr(filters_pkg, name, None)
        if cls is None:
            raise ValueError(f'{name!r} is not a known filter')
        self.register(cls())
