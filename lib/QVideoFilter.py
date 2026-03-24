'''Base classes for image-processing filters in the QVideo filter pipeline.'''
from pyqtgraph.Qt import QtCore, QtWidgets
from QVideo.lib.types import Image


__all__ = ['VideoFilter', 'QVideoFilter']


class VideoFilter(QtCore.QObject):

    '''Base class for video filters.

    Provides a two-stage ``add``/``get`` interface so that subclasses
    can accumulate state across frames (e.g. running averages) before
    returning a result.  The default implementation is a passthrough:
    ``add`` stores the frame and ``get`` returns it unchanged.

    The :meth:`__call__` operator chains :meth:`add` and :meth:`get`
    so that filters can be used as plain callables.
    '''

    def __init__(self) -> None:
        super().__init__()
        self.data: Image | None = None

    def __call__(self, data: Image) -> Image:
        '''Apply the filter to *data* and return the result.

        Parameters
        ----------
        data : Image
            Input frame.

        Returns
        -------
        Image
            Filtered frame.
        '''
        self.add(data)
        return self.get()

    def add(self, data: Image) -> None:
        '''Incorporate a new frame into the filter state.

        Parameters
        ----------
        data : Image
            Input frame.
        '''
        self.data = data

    def get(self) -> Image:
        '''Return the current filter output.

        Returns
        -------
        Image
            Filtered frame.

        Raises
        ------
        RuntimeError
            If called before the first :meth:`add`.
        '''
        if self.data is None:
            raise RuntimeError('get() called before add()')
        return self.data


class QVideoFilter(QtWidgets.QGroupBox):

    '''Widget wrapper for a :class:`VideoFilter` with an enable checkbox.

    Displays the filter as a checkable :class:`~pyqtgraph.Qt.QtWidgets.QGroupBox`.
    When checked the filter is applied to incoming frames; when unchecked
    frames pass through unchanged.

    Subclasses can extend the UI by overriding :meth:`_setupUi`.  The
    override should call ``super()._setupUi()`` first, then add widgets
    to ``self._layout``.

    Parameters
    ----------
    parent : QtWidgets.QWidget
        Parent widget.
    title : str
        Label displayed in the group box border.
    videoFilter : VideoFilter
        The filter to apply when enabled.
    '''

    def __init__(self,
                 parent: QtWidgets.QWidget,
                 title: str,
                 videoFilter: VideoFilter) -> None:
        super().__init__(title, parent)
        self._filter = videoFilter
        self._setupUi()

    @property
    def filter(self) -> VideoFilter:
        '''The :class:`VideoFilter` applied when this widget is enabled.'''
        return self._filter

    @filter.setter
    def filter(self, videoFilter: VideoFilter) -> None:
        if not isinstance(videoFilter, VideoFilter):
            raise TypeError(f'expected VideoFilter, got {type(videoFilter).__name__}')
        self._filter = videoFilter

    def __call__(self, image: Image) -> Image:
        '''Apply the filter if enabled, otherwise return *image* unchanged.

        Parameters
        ----------
        image : Image
            Input frame.

        Returns
        -------
        Image
            Filtered frame if checked, otherwise *image* unchanged.
        '''
        return self.filter(image) if self.isChecked() else image

    def _setupUi(self) -> None:
        '''Configure the group box and create the horizontal layout.

        Subclasses should call ``super()._setupUi()`` and then add their
        own widgets to ``self._layout``.
        '''
        self.setCheckable(True)
        self.setChecked(False)
        self.setFlat(True)
        self._layout = QtWidgets.QHBoxLayout(self)
        self._layout.setContentsMargins(2, 5, 2, 5)

    @classmethod
    def example(cls: 'QVideoFilter') -> None:  # pragma: no cover
        '''Demonstrate the filter widget.

        Intended to be called on a concrete subclass that supplies its
        own ``__init__`` defaults, not on :class:`QVideoFilter` directly.
        '''
        import pyqtgraph as pg

        app = pg.mkQApp()
        widget = cls()
        widget.show()
        pg.exec()
