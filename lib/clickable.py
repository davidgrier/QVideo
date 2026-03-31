# -*- coding: utf-8 -*-
'''Factory that adds a clicked() signal to any QWidget subclass.'''

from qtpy import QtCore, QtGui, QtWidgets


__all__ = ['clickable']


def clickable(widget: QtWidgets.QWidget) -> QtCore.SignalInstance:
    '''Add a ``clicked()`` signal to a widget that does not ordinarily emit one.

    Installs an event filter on *widget* that intercepts
    ``MouseButtonRelease`` events and emits a ``clicked()`` signal.

    Parameters
    ----------
    widget : QWidget
        The widget to make clickable.

    Returns
    -------
    pyqtSignal
        The ``clicked()`` signal attached to *widget*.

    Examples
    --------
    >>> myWidget = QWidget()
    >>> widgetClicked = clickable(myWidget)
    >>> widgetClicked.connect(lambda: print('clicked'))
    '''

    class Filter(QtCore.QObject):

        clicked = QtCore.Signal()

        def eventFilter(self,
                        wid: QtWidgets.QWidget,
                        event: QtGui.QMouseEvent) -> bool:
            if event.type() == QtCore.QEvent.Type.MouseButtonRelease:
                pos = (event.position().toPoint()
                       if hasattr(event, 'position') else event.pos())
                if widget.rect().contains(pos):
                    self.clicked.emit()
                    return True
            return super().eventFilter(wid, event)

    event_filter = Filter(widget)
    widget.installEventFilter(event_filter)
    return event_filter.clicked
