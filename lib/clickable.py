# -*- coding: utf-8 -*-
'''Factory that adds a clicked() signal to any QWidget subclass.'''

from pyqtgraph.Qt.QtCore import QEvent, QObject, pyqtSignal
from pyqtgraph.Qt.QtGui import QMouseEvent
from pyqtgraph.Qt.QtWidgets import QWidget


__all__ = ['clickable']


def clickable(widget: QWidget):
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

    class Filter(QObject):

        clicked = pyqtSignal()

        def eventFilter(self, obj: QObject, event: QMouseEvent) -> bool:
            if event.type() == QEvent.Type.MouseButtonRelease:
                pos = (event.position().toPoint()
                       if hasattr(event, 'position') else event.pos())
                if obj.rect().contains(pos):
                    self.clicked.emit()
                    return True
            return super().eventFilter(obj, event)

    event_filter = Filter(widget)
    widget.installEventFilter(event_filter)
    return event_filter.clicked
