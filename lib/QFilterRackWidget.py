'''Dynamic, reorderable pipeline of QVideoFilter widgets.'''
from collections.abc import Iterator
from qtpy import QtCore, QtWidgets, QtGui
from QVideo.lib.QVideoFilter import (
    QVideoFilter, VideoFilter, renderPipeline)
from QVideo.lib.videotypes import Image
import pyqtgraph as pg


__all__ = ['QFilterRackWidget']


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
        Emitted on drag release, carrying this slot and the global drop
        position.
    hoverRequested : object, QtCore.QPoint
        Emitted during drag, carrying this slot and the current global
        position.
    '''

    removeRequested = QtCore.Signal(object)
    dropRequested = QtCore.Signal(object, QtCore.QPoint)
    hoverRequested = QtCore.Signal(object, QtCore.QPoint)

    def __init__(self,
                 widget: QVideoFilter,
                 parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.widget = widget
        self._setupUi()
        self._connectSignals()

    def _setupUi(self) -> None:
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._handle = _DragHandle(self)
        layout.addWidget(self._handle)
        layout.addWidget(self.widget)
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
    '''Dialog for choosing a filter to add to the rack, by category.'''

    def __init__(self,
                 registry: dict[str, type[QVideoFilter]],
                 parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._setupUi(registry)
        self._connectSignals()

    def _setupUi(self, registry: dict[str, type[QVideoFilter]]) -> None:
        self.setWindowTitle('Add Filter')
        layout = QtWidgets.QVBoxLayout(self)
        self._tree = QtWidgets.QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setRootIsDecorated(True)
        categories: dict[str, QtWidgets.QTreeWidgetItem] = {}
        for name, klass in sorted(registry.items()):
            category = klass.display_category or 'Other'
            if category not in categories:
                cat_item = QtWidgets.QTreeWidgetItem(self._tree, [category])
                cat_item.setFlags(
                    cat_item.flags() & ~QtCore.Qt.ItemFlag.ItemIsSelectable)
                categories[category] = cat_item
            QtWidgets.QTreeWidgetItem(categories[category], [name])
        self._tree.expandAll()
        layout.addWidget(self._tree)
        ok = QtWidgets.QDialogButtonBox.StandardButton.Ok
        cancel = QtWidgets.QDialogButtonBox.StandardButton.Cancel
        self._buttons = QtWidgets.QDialogButtonBox(ok | cancel)
        layout.addWidget(self._buttons)

    def _connectSignals(self) -> None:
        self._tree.itemDoubleClicked.connect(
            lambda item, _col: self.accept() if item.parent() else None)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)

    def selected(self) -> str | None:
        '''Return the selected filter display name, or ``None``.'''
        items = self._tree.selectedItems()
        if not items:
            return None
        item = items[0]
        return item.text(0) if item.parent() else None


class QFilterRackWidget(QtWidgets.QWidget):

    '''A dynamic, reorderable pipeline of
    :class:`~QVideo.lib.QVideoFilter.QVideoFilter` widgets.

    Filters are added interactively via an "Add filter…" toolbar button
    or programmatically via :meth:`add` / :meth:`addByName`.  Each slot
    carries a × button to remove the filter and, when :attr:`editable`
    is ``True``, a ⋮ drag handle to reorder it.  The rack applies each
    filter in pipeline order, honoring each widget's own enabled checkbox.

    The rack is designed for interactive use, where the pipeline should
    be discoverable and adjustable at runtime.  With ``editable=False`` it
    is a fixed panel of filters.

    The widget runs no thread: calling it applies the filters in the
    caller's thread, which suits recorded frames and pipeline design.  To
    filter a live stream use :class:`~QVideo.lib.QFilterRack.QFilterRack`,
    which adds a :class:`~QVideo.lib.QFilterPipeline.QFilterPipeline` that
    runs the switched-on filters on a worker thread.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.  Default: ``None``.
    editable : bool
        If ``False``, the toolbar, drag handles, and close buttons are
        all hidden.  Default: ``True``.
    '''

    #: Emitted when the filters or their order change, or one is switched
    #: on or off.
    filtersChanged = QtCore.Signal()

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
        export_btn = QtWidgets.QPushButton('Export…')
        export_btn.clicked.connect(self._exportDialog)
        layout.addWidget(export_btn)
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
            image = slot.widget(image)
        return image

    def __iter__(self) -> Iterator[QVideoFilter]:
        return (slot.widget for slot in self._iterSlots())

    def activeFilters(self) -> list[VideoFilter]:
        '''The filters that are switched on, in pipeline order.

        These are the :class:`~QVideo.lib.QVideoFilter.VideoFilter`
        objects, not the widgets, so they can be handed to a
        :class:`~QVideo.lib.QFilterPipeline.QFilterPipeline` on another thread.
        '''
        return [widget.filter for widget in self if widget.isChecked()]

    @QtCore.Slot(object, object)
    def switchOff(self, video_filter: VideoFilter, error: Exception) -> None:
        '''Switch off the widget that holds *video_filter*.

        Connected to :attr:`QFilterPipeline.filterFailed`.

        Parameters
        ----------
        video_filter : VideoFilter
            The filter that failed.
        error : Exception
            The exception it raised.
        '''
        for widget in self:
            if widget.filter is video_filter:
                widget.switchOff(error)

    @property
    def filters(self) -> list[QVideoFilter]:
        '''Read-only list of registered filter widgets in pipeline order.'''
        return [slot.widget for slot in self._iterSlots()]

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
        video_filter.toggled.connect(self.filtersChanged)
        self.adjustSize()
        self.filtersChanged.emit()

    @classmethod
    def availableFilters(cls) -> dict[str, type[QVideoFilter]]:
        '''Return the filters that the rack can offer, by display name.

        Returns
        -------
        dict[str, type[QVideoFilter]]
            Each
            :attr:`~QVideo.lib.QVideoFilter.QVideoFilter.display_name`
            of an exported
            :class:`~QVideo.lib.QVideoFilter.QVideoFilter` with a
            non-empty display name, mapped to its class and sorted by
            name.  Iterate it for the names; index it for a class.
        '''
        import QVideo.filters as videofilters  # not at import: it needs lib
        classes = (getattr(videofilters, name, None)
                   for name in videofilters.__all__)
        return dict(sorted(
            (klass.display_name, klass) for klass in classes
            if isinstance(klass, type) and issubclass(klass, QVideoFilter)
            and klass.display_name))

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
        klass = self.availableFilters().get(name)
        if klass is None:
            raise ValueError(f'{name!r} is not a known filter')
        self.add(klass())

    def exportPipeline(self) -> str:
        '''Generate Python source that implements the current enabled pipeline.

        Each enabled filter whose
        :meth:`~QVideo.lib.QVideoFilter.VideoFilter.to_code` returns a
        :class:`~QVideo.lib.QVideoFilter.FilterCode` contributes one code
        block to the generated function.  Filters that are unchecked or
        whose ``to_code`` returns ``None`` are silently skipped with a
        comment.

        Returns
        -------
        str
            Source of a ``filter.py`` module defining
            ``filter(image: np.ndarray) -> np.ndarray``.
        '''
        fragments, skipped = [], []
        for widget in self:
            if widget.isChecked():
                code = widget.filter.to_code()
                if code is None:
                    skipped.append(type(widget.filter).__name__)
                else:
                    fragments.append(code)
        return renderPipeline(fragments, skipped)

    @QtCore.Slot()
    def _exportDialog(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 'Export Pipeline', 'filter.py', 'Python files (*.py)')
        if path:
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(self.exportPipeline())

    def _removeSlot(self, slot: '_FilterSlot') -> None:
        self._slots.removeWidget(slot)
        slot.deleteLater()
        self.adjustSize()
        self.filtersChanged.emit()

    def _slotUnder(self, global_pos: QtCore.QPoint) -> '_FilterSlot | None':
        '''The slot at *global_pos*, or ``None``.'''
        pos = self.mapFromGlobal(global_pos)
        return next((s for s in self._iterSlots()
                     if s.geometry().contains(pos)), None)

    def _hoverSlot(self,
                   slot: '_FilterSlot',
                   hover_pos: QtCore.QPoint) -> None:
        target = self._slotUnder(hover_pos)
        for s in self._iterSlots():
            s.setHighlighted(s is target and s is not slot)

    def _moveSlot(self,
                  slot: '_FilterSlot',
                  drop_pos: QtCore.QPoint) -> None:
        for s in self._iterSlots():
            s.setHighlighted(False)
        target = self._slotUnder(drop_pos)
        if target is None or target is slot:
            return
        target_index = self._slots.indexOf(target)
        self._slots.removeWidget(slot)
        self._slots.insertWidget(target_index, slot)
        self.filtersChanged.emit()

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
    QFilterRackWidget.example()
