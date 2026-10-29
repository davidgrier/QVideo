'''Base class for the control widgets of overlays that analyze frames.'''
import numpy as np
from qtpy import QtCore, QtGui, QtWidgets
from QVideo.lib.videotypes import Image


__all__ = ['QOverlayWidget']


class QOverlayWidget(QtWidgets.QGroupBox):

    '''Control widget of an overlay whose analysis runs on a thread.

    An overlay analyzes the frames of a source, for example to find
    particles, and draws what it finds on a
    :class:`~QVideo.lib.QVideoScreen.QVideoScreen`.  The analysis can take
    longer than a frame, so it runs in a *worker* on a thread of its own.
    This class runs the thread, gives the worker one frame at a time (the
    newest frame that arrives while the worker is busy waits for it),
    passes the results to the graphics item, and shows or hides the item
    with the check box.  It stops the thread when the widget closes and
    when the application quits.

    A subclass supplies three things:

    *worker*
        A :class:`~qtpy.QtCore.QObject` with a slot ``process(image)`` that
        analyzes a frame and emits ``newData(object)`` with the result.
    *overlay*
        The graphics item.  Its ``setFeatures(features)`` receives every
        result.
    :meth:`_setupUi`
        Adds the controls of the worker to the form layout ``self._layout``;
        call ``super()._setupUi()`` first.

    Use ``screen.addOverlay(widget.overlay)`` to register the graphics item
    with a screen, and set :attr:`source` to supply the frames.

    Parameters
    ----------
    title : str
        Label of the group box.
    overlay : QtWidgets.QGraphicsItem
        The graphics item that draws the results.
    worker : QtCore.QObject
        The analysis, which moves to the thread of this widget.
    parent : QtWidgets.QWidget or None
        Parent widget.

    Signals
    -------
    newData(object)
        Emitted with each result of the worker.
    '''

    #: Emitted for each processed frame with the result of the worker.
    newData = QtCore.Signal(object)
    _process = QtCore.Signal(np.ndarray)

    def __init__(self,
                 title: str,
                 overlay: QtWidgets.QGraphicsItem,
                 worker: QtCore.QObject,
                 parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(title, parent)
        self._source = None
        self._ready = True
        self._overlay = overlay
        self._worker = worker
        self._thread = QtCore.QThread(self)
        worker.moveToThread(self._thread)
        self._process.connect(worker.process)
        worker.newData.connect(self._onNewData)
        self._thread.start()
        thread = self._thread
        self.destroyed.connect(lambda: (thread.quit(), thread.wait()))
        self._setupUi()
        QtCore.QCoreApplication.instance().aboutToQuit.connect(self.stop)

    def _setupUi(self) -> None:
        self.setCheckable(True)
        self.setChecked(False)
        self.setFlat(True)
        self._layout = QtWidgets.QFormLayout(self)
        self._layout.setContentsMargins(2, 5, 2, 5)
        self.toggled.connect(self._overlay.setVisible)

    @property
    def source(self):
        '''The :class:`~QVideo.lib.QVideoSource.QVideoSource` analyzed.'''
        return self._source

    @source.setter
    def source(self, source) -> None:
        if self._source is not None:
            self._source.newFrame.disconnect(self._onNewFrame)
        self._source = source
        if source is not None:
            source.newFrame.connect(self._onNewFrame)

    @property
    def overlay(self) -> QtWidgets.QGraphicsItem:
        '''The graphics item that draws the results.'''
        return self._overlay

    @QtCore.Slot(np.ndarray)
    def _onNewFrame(self, image: Image) -> None:
        if self._ready and self.isChecked():
            self._ready = False
            self._process.emit(image)

    @QtCore.Slot(object)
    def _onNewData(self, features) -> None:
        self._ready = True
        self._overlay.setFeatures(features)
        self.newData.emit(features)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        '''Stop the worker thread when the widget is closed.'''
        self.stop()
        super().closeEvent(event)

    @QtCore.Slot()
    def stop(self) -> None:
        '''Disconnect the video source and stop the worker thread.

        The widget also does this when it is deleted and when the
        application quits.  Calling it first, as the last step before the
        widget goes, makes the order explicit (see
        :ref:`shutting-down`).  It is safe to call more than once.
        '''
        self.source = None
        self._thread.quit()
        self._thread.wait()
