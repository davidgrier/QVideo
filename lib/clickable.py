# -*- coding: utf-8 -*-

from pyqtgraph.Qt.QtCore import QEvent, QObject, pyqtSignal
from pyqtgraph.Qt.QtGui import QMouseEvent
from pyqtgraph.Qt.QtWidgets import QWidget


def clickable(widget: QWidget):
    '''Adds a clicked() signal to a widget such as QLineEdit that
    ordinarily does not provide notifications of clicks.

    Example:
    -------
    myWidget = QWidget()
    widgetClicked = clickable(myWidget)
    widgetClicked.connect(lambda: print("clicked"))

    Explanation:
    -----------
    After the call to clickable(), myWidget now processes
    MouseButtonRelease events by emitting the clicked() signal.
    clickable() returns the signal itself for convenience.
    '''

    class Filter(QObject):

        clicked = pyqtSignal()

        def eventFilter(self, obj: QObject, event: QMouseEvent) -> bool:
            if event.type() == QEvent.Type.MouseButtonRelease:
                if obj.rect().contains(event.position().toPoint()):
                    self.clicked.emit()
                    return True
            return super().eventFilter(obj, event)

    event_filter = Filter(widget)
    widget.installEventFilter(event_filter)
    return event_filter.clicked
