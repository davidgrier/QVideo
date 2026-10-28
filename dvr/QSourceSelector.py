'''Radio buttons that choose which stream to record.'''
from typing import Any
from qtpy import QtCore, QtWidgets


__all__ = ['QSourceSelector']


class QSourceSelector(QtWidgets.QGroupBox):

    '''Choose one of several named sources of frames.

    Any object that emits ``newFrame`` is a source: the camera, a filter
    pipeline, the screen.  Add each with a name and the widget makes a
    radio button for it, in a grid, and reports the choice::

        selector = QSourceSelector('Record from')
        selector.addSource('Raw', camera)
        selector.addSource('Filtered', pipeline)
        selector.sourceChanged.connect(set_recorder_source)
        recorder_is_busy.connect(selector.setDisabled)

    The first source added is selected.  Disable the selector while a
    recording runs (``dvr.recording.connect(selector.setDisabled)``): a
    filter may change the size of the frames, and a writer cannot follow.

    Two names may share one source, because the source can be used in two
    ways, such as a screen that records with and without its overlays;
    ``sourceName`` tells them apart.

    Parameters
    ----------
    title : str
        Title of the box.  Default: ``'Record from'``.
    columns : int
        Number of buttons in a row.  Default: 3.
    parent : QWidget
        Parent widget.
    '''

    #: Emitted with the selected source when the choice changes.
    sourceChanged = QtCore.Signal(object)

    def __init__(self,
                 title: str = 'Record from',
                 columns: int = 3,
                 parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(title, parent)
        self.setFlat(True)
        self._columns = columns
        self._grid = QtWidgets.QGridLayout(self)
        self._grid.setContentsMargins(4, 0, 4, 0)
        self._group = QtWidgets.QButtonGroup(self)
        self._sources: dict[QtWidgets.QAbstractButton, Any] = {}
        self._group.buttonToggled.connect(self._onToggled)

    def addSource(self, name: str, source: Any) -> None:
        '''Add a button that selects *source*.

        Parameters
        ----------
        name : str
            Text of the button.
        source : QObject
            Object that emits ``newFrame``.
        '''
        button = QtWidgets.QRadioButton(name)
        row, column = divmod(len(self._sources), self._columns)
        self._grid.addWidget(button, row, column)
        self._group.addButton(button)
        self._sources[button] = source
        if len(self._sources) == 1:
            with QtCore.QSignalBlocker(self._group):
                button.setChecked(True)

    @property
    def source(self) -> Any:
        '''The selected source (``None`` before one is added).'''
        button = self._group.checkedButton()
        return self._sources.get(button)

    @property
    def sourceName(self) -> str | None:
        '''The name of the selected source (``None`` before one is added).'''
        button = self._group.checkedButton()
        return None if button is None else button.text()

    @sourceName.setter
    def sourceName(self, name: str) -> None:
        for button in self._sources:
            if button.text() == name:
                button.setChecked(True)
                return
        raise ValueError(f'No source named {name!r}')

    @QtCore.Slot(QtWidgets.QAbstractButton, bool)
    def _onToggled(self,
                   button: QtWidgets.QAbstractButton,
                   checked: bool) -> None:
        if checked:
            self.sourceChanged.emit(self._sources[button])
