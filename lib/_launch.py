'''Run a camera application: the startup that every demo shares.

:func:`launch` is the whole of it; an application's ``__main__`` block is
one call to it.  What happens, in order:

1. **The command line is read on the main thread**, before anything is
   shown, so that ``-h`` and a bad value end the program here.
2. **A main window and a splash screen appear** at once.  The splash says
   what the program is doing.
3. **The camera opens on a thread of its own**
   (:class:`~QVideo.lib.QCameraOpener.QCameraOpener`), because opening one
   can take seconds (a GenICam camera starts acquiring and reads its whole
   node map) and the splash screen must not freeze.  The thread hands the
   open camera back to the main thread, which owns it from then on.
4. **The interface is built on the main thread.**  The application's widget
   becomes the central widget of the window, the splash screen goes away
   and the window shows.
5. **On quitting**, the opener thread is stopped, and a camera that no
   window ever took is closed.

If the camera cannot open, or the widget needs a package that is not
installed, the splash screen closes and the program ends with the message.
'''
import sys
from typing import TYPE_CHECKING

# qtpy comes first: it selects the Qt binding (QT_API), and pyqtgraph then
# uses whichever binding is loaded.  Imported first, pyqtgraph would choose
# its own and ignore QT_API.
from qtpy import QtGui, QtWidgets
import pyqtgraph as pg

from QVideo.lib._splash import say, splash
from QVideo.lib.QCameraOpener import QCameraOpener
from QVideo.cameras import chooser

if TYPE_CHECKING:
    from QVideo.lib.QCamera import QCamera


__all__ = ['launch']


class _Launcher:

    '''The window, the splash screen and the opener of one application.

    It holds what the steps of the startup share, so that each step is a
    method: :meth:`run` shows the splash screen and starts the opener,
    :meth:`build` makes the interface when the camera is open,
    :meth:`fail` ends the program, and :meth:`finish` cleans up when the
    application quits.

    Parameters
    ----------
    app : QApplication
        The application, which ends when the window closes or on Ctrl+Q.
    widget : type
        Class of the central widget.
    title : str or None
        Name of the application and title of the window.
    kwargs : dict
        Keyword arguments for *widget*.

    Attributes
    ----------
    problems : list of str
        Messages that end the program; the first is its exit message.
    '''

    def __init__(self, app: QtWidgets.QApplication,
                 widget: type[QtWidgets.QWidget],
                 title: str | None, kwargs: dict) -> None:
        self.app = app
        self.widget = widget
        self.kwargs = kwargs
        self.problems: list[str] = []
        self.window = QtWidgets.QMainWindow()
        self.window.setWindowTitle(title or '')
        QtWidgets.QShortcut(QtGui.QKeySequence('Ctrl+Q'),
                            self.window).activated.connect(app.quit)
        self.screen = splash(title)
        self.opener = QCameraOpener()
        self.opener.opened.connect(self.build)
        self.opener.failed.connect(lambda why: self.fail(f'Error: {why}'))
        app.aboutToQuit.connect(self.finish)

    def run(self) -> None:
        '''Show the splash screen, start the opener and run the application.

        Returns when the application quits.
        '''
        self.screen.show()
        # macOS shows a splash screen only if it is also raised and
        # activated.
        self.screen.raise_()
        self.screen.activateWindow()
        say(self.screen, 'Opening the camera...')
        self.opener.start()
        pg.exec()

    def build(self, key: str, camera: 'QCamera') -> None:
        '''Make the interface for the open *camera* and show the window.

        Called on the main thread when the opener has the camera.  A widget
        that raises ``ImportError`` (it needs a package that is not
        installed) ends the program with that message.
        '''
        say(self.screen, 'Building the interface...')
        try:
            central = self.widget(chooser.make_tree(key, camera).start(),
                                  **self.kwargs)
        except ImportError as error:
            self.fail(f'Error: {error}')
            return
        self.opener.camera = None       # the interface has it now
        self.window.setCentralWidget(central)
        if hasattr(central, 'message'):
            central.message.connect(self.window.statusBar().showMessage)
        self.window.show()
        self.screen.finish(self.window)

    def fail(self, message: str) -> None:
        '''End the program with *message*: close the splash screen, quit.'''
        self.problems.append(message)
        self.screen.close()
        self.app.quit()

    def finish(self) -> None:
        '''Clean up as the application quits.

        Stops the opener, which closes a camera that was opened but never
        given to a window (the application quit while the camera was still
        opening), and closes the splash screen.
        '''
        self.opener.stop()
        self.screen.close()


def launch(widget: type[QtWidgets.QWidget],
           title: str | None = None,
           **kwargs) -> None:
    '''Show *widget* for a camera chosen on the command line, and run it.

    The camera backend comes from the command-line flags added by
    :func:`~QVideo.cameras.chooser.camera_parser` (a noise camera if there are
    none).  A splash screen appears at once and says what is happening; the
    camera opens on a thread of its own, so that a slow camera never freezes
    it.  The widget then becomes the central widget of the
    :class:`~qtpy.QtWidgets.QMainWindow`, which is how applications embed
    QVideo components, so that sizing and shutdown are exercised in that
    setting.  The window has a status bar that shows the messages of a widget
    with a ``message(str)`` signal, and it closes on Ctrl+Q.  A widget that
    needs an optional package that is not installed ends the program with the
    error message.  Quitting stops every thread that the components own (see
    :ref:`shutting-down`).

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
    # -h and a bad value end the program here, on the main thread: argparse
    # exits by raising SystemExit, which would only end the opener's thread
    # and leave the splash screen waiting for a camera.
    chooser.camera_parser().parse_known_args()
    launcher = _Launcher(pg.mkQApp(title), widget, title, kwargs)
    launcher.run()
    if launcher.problems:
        sys.exit(launcher.problems[0])
