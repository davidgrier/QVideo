'''Run a camera application: the startup that every demo shares.'''
import sys
import pyqtgraph as pg
from qtpy import QtCore, QtGui, QtWidgets
from QVideo.lib._splash import say, splash
from QVideo.cameras import chooser


__all__ = ['launch']


class _Opener(QtCore.QThread):

    '''Open the camera chosen on the command line, off the GUI thread.

    Opening a camera can take seconds (a GenICam camera starts acquiring
    and reads its whole node map), and the window must not wait for it.
    '''

    #: The backend key and the open camera.
    opened = QtCore.Signal(str, object)
    #: Why no camera could be opened.
    failed = QtCore.Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.camera = None

    def run(self) -> None:
        try:
            key, self.camera = chooser.open_camera()
        except Exception as error:
            self.failed.emit(str(error))
            return
        if self.isInterruptionRequested():  # the application is quitting
            return
        # A QObject can be moved only by the thread that it lives in.
        self.camera.moveToThread(QtCore.QCoreApplication.instance().thread())
        self.opened.emit(key, self.camera)


def launch(widget: type[QtWidgets.QWidget],
           title: str | None = None,
           **kwargs) -> None:
    '''Show *widget* for a camera chosen on the command line, and run it.

    The camera backend comes from the command-line flags described in
    :func:`~QVideo.cameras.chooser.choose_camera` (a noise camera if there are
    none).  A splash screen appears at once and says what is happening;
    the camera opens on a thread of its own, so that a slow camera never
    freezes it.  The widget then becomes the central widget
    of the :class:`~qtpy.QtWidgets.QMainWindow`, which is how applications
    embed QVideo components, so that sizing and shutdown are exercised in
    that setting.  The window has a status bar that shows the messages of a
    widget with a ``message(str)`` signal, and it closes on Ctrl+Q.  A
    widget that needs an optional package that is not installed ends the
    program with the error message.  Quitting stops every thread that the
    components own (see :ref:`shutting-down`).

    Parameters
    ----------
    widget : type
        Class of the central widget.  It is called with the camera tree as
        its first argument, as :class:`~QVideo.demos.demo.Demo` and
        :class:`~QVideo.QCamcorder.QCamcorder` expect.
    title : str, optional
        Name of the application and title of the window.
    **kwargs :
        Further keyword arguments for *widget*.

    Examples
    --------
    ::

        from QVideo.lib import launch
        from QVideo.demos import HistogramDemo

        launch(HistogramDemo, 'Histogram Demo')
    '''
    app = pg.mkQApp(title)
    window = QtWidgets.QMainWindow()
    window.setWindowTitle(title or '')
    QtWidgets.QShortcut(
        QtGui.QKeySequence('Ctrl+Q'), window).activated.connect(app.quit)
    screen = splash(title)
    problems = []
    opener = _Opener()

    def fail(message: str) -> None:
        problems.append(message)
        screen.close()
        app.quit()

    def build(key: str, camera) -> None:
        say(screen, 'Building the interface...')
        try:
            central = widget(chooser.make_tree(key, camera).start(), **kwargs)
        except ImportError as error:
            fail(f'Error: {error}')
            return
        window.setCentralWidget(central)
        if hasattr(central, 'message'):
            central.message.connect(window.statusBar().showMessage)
        window.show()
        screen.finish(window)

    def finish() -> None:
        opener.requestInterruption()
        opener.wait()
        screen.close()
        if opener.camera is not None and window.centralWidget() is None:
            opener.camera.close()

    opener.opened.connect(build)
    opener.failed.connect(lambda why: fail(f'Error: {why}'))
    app.aboutToQuit.connect(finish)
    screen.show()
    # macOS shows a splash screen only if it is also raised and activated.
    screen.raise_()
    screen.activateWindow()
    say(screen, 'Opening the camera...')
    opener.start()
    pg.exec()
    if problems:
        sys.exit(problems[0])
