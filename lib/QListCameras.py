from pyqtgraph import ComboBox
from pyqtgraph.Qt.QtCore import pyqtSignal, pyqtSlot


class QListCameras(ComboBox):
    '''A QComboBox that lists available cameras.

    Inherits
    --------
    pyqtgraph.ComboBox

    Methods
    -------
    refresh()
        Refresh the list of available cameras.

    Signals
    -------
    cameraSelected(model: type, index: int)
        Emitted when a camera is selected from the combo box.
    '''

    cameraSelected = pyqtSignal(type, int)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.currentIndexChanged.connect(self.cameraSelection)
        self.refresh()

    def refresh(self) -> None:
        '''Refresh the list of available cameras.'''
        self.clear()
        self.addItem('Select Camera', -1)
        self._listCameras()

    def _listCameras(self) -> None:
        '''List available cameras and populate the combo box.

        This method should be overridden in subclasses
        '''
        pass

    def _model(self) -> type:
        '''Return the camera model class.

        This method should be overridden in subclasses
        '''
        return None

    @pyqtSlot(int)
    def cameraSelection(self, index: int) -> None:
        self.cameraSelected.emit(self._model(), self.currentData())

    @classmethod
    def example(cls):
        import pyqtgraph as pg
        from pyqtgraph.Qt.QtCore import pyqtSlot

        @pyqtSlot(int, str)
        def on_camera_changed(model: type, index: int) -> None:
            print(f'Selected {model.__name__} {index = }')

        app = pg.mkQApp(f'{cls.__name__} Example')
        combo = cls()
        combo.cameraSelected.connect(on_camera_changed)
        combo.show()
        app.exec()
