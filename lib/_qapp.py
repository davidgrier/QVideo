'''The application that a camera needs before it is made.'''
from collections.abc import Callable

from qtpy import QtCore

__all__ = ['ensure_qapp', 'stopAtQuit']

#: Keeps the application that :func:`ensure_qapp` makes alive.
_keep: list = []


def stopAtQuit(slot: Callable[[], object]) -> None:
    '''Call *slot* when the application is about to quit.

    A thread must not be running when Python tears down: Qt aborts a
    running ``QThread`` that it deletes.  A widget that owns a thread stops
    it in ``closeEvent`` and when it is destroyed.  An object that no widget
    owns (a recorder, a pipeline) cannot count on either, and uses this: it
    connects the slot to ``QCoreApplication.aboutToQuit``, the signal that Qt
    emits while the event loop is still able to deliver what the slot does.
    It is for a program with an application and does nothing without one.
    The slot is a bound method of a ``QObject``, so Qt drops the connection
    when the object is deleted.
    '''
    app = QtCore.QCoreApplication.instance()
    if app is not None:
        app.aboutToQuit.connect(slot)


def ensure_qapp() -> None:
    '''Create a QApplication if none exists (required before any QCamera).

    The application is kept in a module variable: if nothing refers to it,
    Python deletes it again as soon as this function returns.
    '''
    from qtpy.QtWidgets import QApplication
    if QApplication.instance() is None:
        _keep.append(QApplication([]))
