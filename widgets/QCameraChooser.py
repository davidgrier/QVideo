'''A combo box of the cameras that can be opened.'''
from qtpy import QtCore, QtWidgets
from QVideo.cameras.chooser import available_cameras


__all__ = ['QCameraChooser']


class _Scanner(QtCore.QThread):

    '''Look for cameras on a thread of its own.

    Opening each device to see that it works can take seconds, and the
    window must not wait for it.
    '''

    #: The cameras that were found, as ``available_cameras()`` lists them.
    found = QtCore.Signal(list)

    def run(self) -> None:
        cameras = available_cameras()
        if not self.isInterruptionRequested():  # the chooser is gone
            self.found.emit(cameras)


class QCameraChooser(QtWidgets.QComboBox):

    '''A combo box that lists the cameras that work, and lets the user
    choose one.

    The chooser looks for cameras when it is made, and again when
    :meth:`refresh` is called, on a thread of its own: it says that it is
    looking, and the window does not freeze while each device is opened to
    see that it works (which can make the light of a camera blink).  The
    simulated Noise camera is always listed.

    Choosing an entry emits :attr:`cameraSelected` with the arguments of
    :func:`~QVideo.Camera`, which opens it::

        chooser = QCameraChooser()
        chooser.cameraSelected.connect(
            lambda model, cameraID: print(Camera(model, cameraID)))

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.
    scan : bool
        Look for cameras at once.  Default: ``True``.

    Signals
    -------
    cameraSelected(str, int)
        The user chose a camera: the model and the camera ID.
    scanned()
        A search for cameras ended and the list is complete.
    '''

    #: The user chose a camera: its model and camera ID.
    cameraSelected = QtCore.Signal(str, int)
    #: A search ended and the list is complete.
    scanned = QtCore.Signal()

    def __init__(self,
                 parent: QtWidgets.QWidget | None = None,
                 scan: bool = True) -> None:
        super().__init__(parent)
        self._scanner: _Scanner | None = None
        self.activated.connect(self._onActivated)
        QtCore.QCoreApplication.instance().aboutToQuit.connect(self.stop)
        if scan:
            self.refresh()

    def refresh(self) -> None:
        '''Look for cameras again.

        Does nothing while a search is going on.
        '''
        if self._scanner is not None:
            return
        self.clear()
        self.addItem('Looking for cameras...')
        self.setEnabled(False)
        scanner = self._scanner = _Scanner()  # a thread takes no parent
        scanner.found.connect(self._setCameras)
        self.destroyed.connect(
            lambda: (scanner.requestInterruption(), scanner.wait()))
        scanner.start()

    def camera(self) -> tuple[str, int] | None:
        '''Return the model and camera ID of the chosen camera, or ``None``
        while the chooser is looking.'''
        return self.currentData()

    @QtCore.Slot(list)
    def _setCameras(self, cameras: list[tuple[str, int, str]]) -> None:
        scanner, self._scanner = self._scanner, None
        if scanner is None:  # stopped after the result was on its way
            return
        scanner.wait()
        self.clear()
        for model, cameraID, name in cameras:
            text = f'{model} {cameraID}'
            if name != model:
                text += f': {name}'
            self.addItem(text, (model, cameraID))
        self.setEnabled(True)
        self.scanned.emit()

    @QtCore.Slot(int)
    def _onActivated(self, index: int) -> None:
        camera = self.itemData(index)
        if camera is not None:
            self.cameraSelected.emit(*camera)

    @QtCore.Slot()
    def stop(self) -> None:
        '''Stop looking for cameras, and wait for the search to end.

        The chooser also does this when it is deleted and when the
        application quits.  It is safe to call more than once.
        '''
        scanner, self._scanner = self._scanner, None
        if scanner is not None:
            scanner.requestInterruption()
            scanner.wait()


if __name__ == '__main__':  # pragma: no cover
    import sys
    app = QtWidgets.QApplication(sys.argv)
    chooser = QCameraChooser()
    chooser.cameraSelected.connect(
        lambda model, cameraID: print(f'Camera({model!r}, {cameraID})'))
    chooser.show()
    sys.exit(app.exec())
