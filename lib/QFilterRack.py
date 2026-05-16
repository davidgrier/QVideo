'''Dynamic, reorderable pipeline of QVideoFilter widgets.'''
from collections.abc import Iterator
from qtpy import QtCore, QtWidgets, QtGui
from QVideo.lib.QVideoFilter import QVideoFilter
from QVideo.lib.videotypes import Image
import QVideo.filters as videofilters
import pyqtgraph as pg


__all__ = ['QFilterRack']


class _DragHandle(QtWidgets.QLabel):
    '''Grip that initiates slot reordering via mouse drag.

    Signals
    -------
    dragging : QtCore.QPoint
        Global cursor position, emitted continuously during a left-button drag.
    dropped : QtCore.QPoint
        Global cursor position, emitted on left-button release.
    '''

    dragging = QtCore.Signal(QtCore.QPoint)
    dropped = QtCore.Signal(QtCore.QPoint)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__('⋮', parent)
        self.setFixedWidth(14)
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.buttons() & QtCore.Qt.MouseButton.LeftButton:
            self.dragging.emit(QtGui.QCursor.pos())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        self.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.dropped.emit(QtGui.QCursor.pos())
        super().mouseReleaseEvent(event)


class _FilterSlot(QtWidgets.QWidget):
    '''Wraps one :class:`~QVideo.lib.QVideoFilter.QVideoFilter` with a
    drag handle and a × close button.

    The drag handle (⋮) and close button are shown only when the slot
    is editable.  A 3 px highlight bar is shown across the top of the
    slot while another slot is being dragged over it.

    Signals
    -------
    removeRequested : object
        Emitted when × is clicked, carrying this slot.
    dropRequested : object, QtCore.QPoint
        Emitted on drag release, carrying this slot and the global drop position.
    hoverRequested : object, QtCore.QPoint
        Emitted during drag, carrying this slot and the current global position.
    '''

    removeRequested = QtCore.Signal(object)
    dropRequested = QtCore.Signal(object, QtCore.QPoint)
    hoverRequested = QtCore.Signal(object, QtCore.QPoint)

    def __init__(self,
                 widget: QVideoFilter,
                 parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._widget = widget
        self._setupUi()
        self._connectSignals()

    def _setupUi(self) -> None:
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._handle = _DragHandle(self)
        layout.addWidget(self._handle)
        layout.addWidget(self._widget)
        self._closeButton = QtWidgets.QPushButton('×', self)
        self._closeButton.setFixedSize(18, 18)
        self._closeButton.setFlat(True)
        self._dropIndicator = QtWidgets.QFrame(self)
        self._dropIndicator.setFixedHeight(3)
        self._dropIndicator.setStyleSheet('background: palette(highlight);')
        self._dropIndicator.setVisible(False)

    def _connectSignals(self) -> None:
        self._closeButton.clicked.connect(
            lambda: self.removeRequested.emit(self))
        self._handle.dropped.connect(
            lambda pos: self.dropRequested.emit(self, pos))
        self._handle.dragging.connect(
            lambda pos: self.hoverRequested.emit(self, pos))

    def setEditable(self, editable: bool) -> None:
        '''Show or hide the drag handle and close button.

        Parameters
        ----------
        editable : bool
            ``True`` to show edit controls; ``False`` to hide them.
        '''
        self._handle.setVisible(editable)
        self._closeButton.setVisible(editable)

    def setHighlighted(self, highlighted: bool) -> None:
        '''Show or hide the drop-target indicator.

        Parameters
        ----------
        highlighted : bool
            ``True`` to show the 3 px highlight bar; ``False`` to hide it.
        '''
        self._dropIndicator.setVisible(highlighted)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        btn = self._closeButton
        btn.move(self.width() - btn.width() - 2, 2)
        btn.raise_()
        self._dropIndicator.resize(self.width(), 3)
        self._dropIndicator.move(0, 0)
        self._dropIndicator.raise_()


class _FilterPicker(QtWidgets.QDialog):
    '''Dialog for selecting a filter to add to the rack.'''

    def __init__(self,
                 filters: list[str],
                 parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._setupUi(filters)
        self._connectSignals()

    def _setupUi(self, filters: list[str]) -> None:
        self.setWindowTitle('Add Filter')
        layout = QtWidgets.QVBoxLayout(self)
        self._list = QtWidgets.QListWidget()
        self._list.addItems(filters)
        layout.addWidget(self._list)
        ok = QtWidgets.QDialogButtonBox.StandardButton.Ok
        cancel = QtWidgets.QDialogButtonBox.StandardButton.Cancel
        self._buttons = QtWidgets.QDialogButtonBox(ok | cancel)
        layout.addWidget(self._buttons)

    def _connectSignals(self) -> None:
        self._list.itemDoubleClicked.connect(self.accept)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)

    def selected(self) -> str | None:
        '''Return the selected filter class name, or ``None``.'''
        items = self._list.selectedItems()
        return items[0].text() if items else None


class QFilterRack(QtWidgets.QWidget):

    '''A dynamic, reorderable pipeline of :class:`~QVideo.lib.QVideoFilter.QVideoFilter` widgets.

    Filters are added interactively via an "Add filter…" toolbar button
    or programmatically via :meth:`add` / :meth:`addByName`.  Each slot
    carries a × button to remove the filter and, when :attr:`editable`
    is ``True``, a ⋮ drag handle to reorder it.  The rack applies each
    filter in pipeline order, honoring each widget's own enabled checkbox.

    Unlike :class:`~QVideo.lib.QFilterBank.QFilterBank`, which is
    configured programmatically and holds a fixed set of filters,
    ``QFilterRack`` is designed for interactive use where the pipeline
    should be discoverable and adjustable at runtime.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.  Default: ``None``.
    editable : bool
        If ``False``, the toolbar, drag handles, and close buttons are
        all hidden.  Default: ``True``.
    '''

    def __init__(self,
                 parent: QtWidgets.QWidget | None = None,
                 editable: bool = True) -> None:
        super().__init__(parent)
        self._editable = editable
        self._setupUi()

    def _setupUi(self) -> None:
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self._toolbar = self._makeToolbar()
        self._toolbar.setVisible(self._editable)
        outer.addWidget(self._toolbar)
        self._slots = QtWidgets.QVBoxLayout()
        self._slots.setContentsMargins(0, 0, 0, 0)
        self._slots.setSpacing(0)
        outer.addLayout(self._slots)
        outer.addStretch()

    def _makeToolbar(self) -> QtWidgets.QWidget:
        bar = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(bar)
        layout.setContentsMargins(4, 4, 4, 0)
        btn = QtWidgets.QPushButton('Add filter…')
        btn.clicked.connect(self._addFilterDialog)
        layout.addWidget(btn)
        layout.addStretch()
        return bar

    def _slotAt(self, index: int) -> '_FilterSlot | None':
        item = self._slots.itemAt(index)
        return item.widget() if item else None

    def _iterSlots(self) -> Iterator['_FilterSlot']:
        for i in range(self._slots.count()):
            if slot := self._slotAt(i):
                yield slot

    def __call__(self, image: Image) -> Image | None:
        '''Apply all registered filters to *image* in order.

        Parameters
        ----------
        image : Image
            Input frame.

        Returns
        -------
        Image or None
            Frame after all enabled filters have been applied.
        '''
        for slot in self._iterSlots():
            image = slot._widget(image)
        return image

    def __iter__(self) -> Iterator[QVideoFilter]:
        return (slot._widget for slot in self._iterSlots())

    @property
    def filters(self) -> list[QVideoFilter]:
        '''Read-only list of registered filter widgets in pipeline order.'''
        return [slot._widget for slot in self._iterSlots()]

    @property
    def editable(self) -> bool:
        '''bool: whether the user can add, remove, or reorder filters.'''
        return self._editable

    @editable.setter
    def editable(self, value: bool) -> None:
        self._editable = value
        self._toolbar.setVisible(value)
        for slot in self._iterSlots():
            slot.setEditable(value)

    def add(self, video_filter: QVideoFilter) -> None:
        '''Add a filter widget to the end of the rack.

        Parameters
        ----------
        video_filter : QVideoFilter
            Filter widget to add.

        Raises
        ------
        TypeError
            If *video_filter* is not a
            :class:`~QVideo.lib.QVideoFilter.QVideoFilter` instance.
        '''
        if not isinstance(video_filter, QVideoFilter):
            raise TypeError(f'expected QVideoFilter, '
                            f'got {type(video_filter).__name__}')
        slot = _FilterSlot(video_filter, self)
        slot.removeRequested.connect(self._removeSlot)
        slot.dropRequested.connect(self._moveSlot)
        slot.hoverRequested.connect(self._hoverSlot)
        slot.setEditable(self._editable)
        self._slots.addWidget(slot)
        self.adjustSize()

    @classmethod
    def _registry(cls) -> dict[str, type[QVideoFilter]]:
        '''Map :attr:`~QVideo.lib.QVideoFilter.QVideoFilter.display_name`
        to class for every exported :class:`~QVideo.lib.QVideoFilter.QVideoFilter`
        that has a non-empty :attr:`display_name`.
        '''
        return {
            klass.display_name: klass
            for name in videofilters.__all__
            if isinstance(klass := getattr(videofilters, name, None), type)
            and issubclass(klass, QVideoFilter)
            and klass.display_name
        }

    def addByName(self, name: str) -> None:
        '''Instantiate a filter by display name and add it to the rack.

        Parameters
        ----------
        name : str
            :attr:`~QVideo.lib.QVideoFilter.QVideoFilter.display_name` of
            the filter to add.

        Raises
        ------
        ValueError
            If *name* does not match any registered filter.
        '''
        klass = self._registry().get(name)
        if klass is None:
            raise ValueError(f'{name!r} is not a known filter')
        self.add(klass())

    @classmethod
    def availableFilters(cls) -> list[str]:
        '''Return display names of all available filters, sorted.

        Returns
        -------
        list[str]
            Sorted list of :attr:`~QVideo.lib.QVideoFilter.QVideoFilter.display_name`
            values for every exported filter with a non-empty display name.
        '''
        return sorted(cls._registry())

    def _removeSlot(self, slot: '_FilterSlot') -> None:
        self._slots.removeWidget(slot)
        slot.deleteLater()
        self.adjustSize()

    def _hoverSlot(self,
                   slot: '_FilterSlot',
                   hover_pos: QtCore.QPoint) -> None:
        local_pos = self.mapFromGlobal(hover_pos)
        target = next(
            (w for w in self._iterSlots() if w.geometry().contains(local_pos)),
            None)
        for s in self._iterSlots():
            s.setHighlighted(s is target and s is not slot)

    def _moveSlot(self,
                  slot: '_FilterSlot',
                  drop_pos: QtCore.QPoint) -> None:
        for s in self._iterSlots():
            s.setHighlighted(False)
        local_pos = self.mapFromGlobal(drop_pos)
        target = next(
            (w for w in self._iterSlots()
             if w.geometry().contains(local_pos)),
            None)
        if target is None or target is slot:
            return
        target_index = self._slots.indexOf(target)
        self._slots.removeWidget(slot)
        self._slots.insertWidget(target_index, slot)

    def _addFilterDialog(self) -> None:
        available = self.availableFilters()
        if not available:
            return
        picker = _FilterPicker(available, self)
        if picker.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            name = picker.selected()
            if name:
                self.addByName(name)

    @classmethod
    def example(cls) -> None:  # pragma: no cover
        '''Display an empty, editable filter rack.'''
        pg.mkQApp()
        rack = cls()
        rack.show()
        pg.exec()


if __name__ == '__main__':  # pragma: no cover
    QFilterRack.example()
