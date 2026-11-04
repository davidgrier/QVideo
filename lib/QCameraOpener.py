'''Opens the camera that the command line names, off the GUI thread.'''
from __future__ import annotations

from argparse import ArgumentParser

from qtpy import QtCore

from QVideo.cameras import chooser
from QVideo.lib.QCamera import QCamera


__all__ = ['QCameraOpener']


class QCameraOpener(QtCore.QThread):

    '''Opens the camera that the command line chooses, in a thread.

    Opening a camera can take seconds (a GenICam camera starts acquiring
    and reads its whole node map), and a window must not wait for it.
    While the camera opens, the rest of a program can start: it shows a
    splash screen, makes its other hardware, and asks for the camera
    when it needs it.  :func:`~QVideo.lib.launch` is the whole of that for
    an application that needs nothing else; a program that does, such as
    one that has to open a second device while the camera opens, uses the
    opener itself::

        opener = QCameraOpener(parser)
        opener.start()
        make_the_other_hardware()
        if not opener.waitForCamera():
            sys.exit(opener.reason)
        window = Window(chooser.make_tree(opener.key, opener.camera))
        opener.camera = None        # the window has it now

    The camera is made in this thread and handed to the thread of the
    application when it is open, because a Qt object can be moved only by
    the thread that it lives in.

    Parameters
    ----------
    parser : ArgumentParser or None
        The parser that holds the camera flags, as
        :func:`~QVideo.cameras.chooser.open_camera` takes it.  A program
        with flags of its own passes the parser that has them all.
        Default: a parser of the camera flags only.
    parent : QtCore.QObject or None
        Qt parent object.

    Attributes
    ----------
    camera : QCamera or None
        The open camera, once ``opened`` has been emitted.  Whoever takes
        the camera sets this to ``None``, so that :meth:`stop` closes only
        a camera that nobody took.
    key : str or None
        The key of the backend that opened it.
    reason : str or None
        Why no camera could be opened, if that happened.

    Signals
    -------
    opened : Signal(str, object)
        The key of the backend and the open camera.
    failed : Signal(str)
        Why no camera could be opened.
    '''

    #: Emitted with the key of the backend and the open camera.
    opened = QtCore.Signal(str, object)
    #: Emitted with the reason that no camera could be opened.
    failed = QtCore.Signal(str)

    def __init__(self,
                 parser: ArgumentParser | None = None,
                 parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._parser = parser
        self.camera: QCamera | None = None
        self.key: str | None = None
        self.reason: str | None = None

    def run(self) -> None:
        '''Open the camera and report; this runs in the thread.

        Emits :attr:`opened` with the key of the backend and the camera,
        or :attr:`failed` with the reason.  Emits neither, and closes the
        camera, if the application is quitting.
        '''
        try:
            key, camera = chooser.open_camera(self._parser)
        except Exception as error:
            self.reason = str(error)
            self.failed.emit(self.reason)
            return
        if self.isInterruptionRequested():  # the application is quitting
            camera.close()
            return
        camera.moveToThread(QtCore.QCoreApplication.instance().thread())
        self.key, self.camera = key, camera
        self.opened.emit(key, camera)

    def waitForCamera(self) -> bool:
        '''Wait, with the event loop running, until the thread is done.

        The splash screen and the rest of the interface stay alive.

        Returns
        -------
        bool
            Whether a camera was opened.
        '''
        loop = QtCore.QEventLoop()
        self.finished.connect(loop.quit)
        if self.isRunning():
            loop.exec()
        self.wait()
        return self.camera is not None

    def stop(self) -> None:
        '''Ask the thread to stop, wait for it, and close its camera.

        For use when the application quits.  A camera that something else
        has taken (:attr:`camera` is ``None``) is left alone.
        '''
        self.requestInterruption()
        self.wait()
        if self.camera is not None:
            self.camera.close()
            self.camera = None
