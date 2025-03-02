# -*- coding: utf-8 -*-

from PyQt5.QtCore import (QObject, pyqtSignal, QEvent)
from PyQt5.QtWidgets import QWidget


def clickable(widget: QWidget) -> pyqtSignal:
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
    clicked() returns the signal itself for convenience.
    '''

    class Filter(QObject):

        clicked = pyqtSignal()

        def eventFilter(self, obj: QObject, event: QEvent) -> bool:
            if obj == widget:
                if event.type() == QEvent.MouseButtonRelease:
                    if obj.rect().contains(event.pos()):
                        self.clicked.emit()
                        return True
            return False

    filter = Filter(widget)
    widget.installEventFilter(filter)
    return filter.clicked
