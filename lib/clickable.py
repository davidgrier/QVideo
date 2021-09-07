# -*- coding: utf-8 -*-

from PyQt5.QtCore import (QObject, pyqtSignal, QEvent)


def clickable(widget):
    """Adds a clicked signal to a widget such as QLineEdit that
    ordinarily does not provide notifications of clicks."""

    class Filter(QObject):

        clicked = pyqtSignal()

        def eventFilter(self, obj, event):
            if obj == widget:
                if event.type() == QEvent.MouseButtonRelease:
                    if obj.rect().contains(event.pos()):
                        self.clicked.emit()
                        return True
            return False

    filter = Filter(widget)
    widget.installEventFilter(filter)
    return filter.clicked
