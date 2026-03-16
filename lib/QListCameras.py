from pyqtgraph import ComboBox
from pyqtgraph.Qt.QtCore import pyqtSignal, pyqtSlot


__all__ = ['QListCameras']


class QListCameras(ComboBox):
    '''Base class for a combo box that lists available cameras.

    Subclasses should override :meth:`_listCameras` to populate the
    combo box with available camera entries, and :meth:`_model` to
    return the camera class associated with entries.

    Inherits
    --------
    pyqtgraph.ComboBox

    Signals
    -------
    cameraSelected(model: type, index: int)
        Emitted when a camera entry is selected. ``model`` is the
        camera class returned by :meth:`_model` and ``index`` is the
        device index stored as the item's data.

    Methods
    -------
    refresh()
        Clear and repopulate the list of available cameras.
    '''

    cameraSelected = pyqtSignal(type, int)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.currentIndexChanged.connect(self.cameraSelection)
        self.refresh()

    def refresh(self) -> None:
        '''Clear and repopulate the list of available cameras.'''
        self.clear()
        self.addItem('Select Camera', -1)
        self._listCameras()

    def _listCameras(self) -> None:
        '''Populate the combo box with available camera entries.

        Override in subclasses to add camera-specific items via
        ``self.addItem(label, device_index)``.
        '''
        raise NotImplementedError

    def _model(self) -> type:
        '''Return the camera model class for selected entries.

        Override in subclasses to return the appropriate camera class.
        '''
        raise NotImplementedError

    @pyqtSlot(int)
    def cameraSelection(self, row: int) -> None:
        '''Emit :attr:`cameraSelected` for the current combo box entry.

        The placeholder "Select Camera" entry (row 0) and an empty
        combo box (row -1) are ignored and do not emit the signal.

        Parameters
        ----------
        row : int
            The combo box row index of the newly selected item.
        '''
        if row > 0:
            self.cameraSelected.emit(self._model(), self.currentData())

    @classmethod
    def example(cls):  # pragma: no cover
        import pyqtgraph as pg

        @pyqtSlot(type, int)
        def on_camera_changed(model: type, index: int) -> None:
            print(f'Selected {model.__name__} {index = }')

        app = pg.mkQApp(f'{cls.__name__} Example')
        combo = cls()
        combo.cameraSelected.connect(on_camera_changed)
        combo.show()
        app.exec()
