'''A panel of controls that scrolls when the window is too short for it.'''
from qtpy import QtCore, QtWidgets


__all__ = ['QScrollPanel']


class QScrollPanel(QtWidgets.QScrollArea):

    '''Shows a panel of controls at its natural size, and scrolls it.

    The panel is as wide as its contents, plus room for a vertical scroll
    bar, and as tall as its contents when the window has room for that.
    When the window is shorter, the bar appears and the panel scrolls.
    There is never a horizontal bar, and the panel follows its contents
    when they change size.

    Parameters
    ----------
    panel : QWidget
        The panel of controls, with a layout.
    parent : QWidget, optional
        Parent widget.
    '''

    def __init__(self,
                 panel: QtWidgets.QWidget,
                 parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidget(panel)
        self.setWidgetResizable(True)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        panel.installEventFilter(self)

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        '''Tell the layout that this widget wants a new size.'''
        if (obj is self.widget()
                and event.type() == QtCore.QEvent.LayoutRequest):
            self.updateGeometry()
        return super().eventFilter(obj, event)

    def sizeHint(self) -> QtCore.QSize:
        '''Return the size of the panel, with room for the scroll bar.'''
        hint = self.widget().sizeHint()
        bar = self.style().pixelMetric(
            QtWidgets.QStyle.PixelMetric.PM_ScrollBarExtent)
        return QtCore.QSize(hint.width() + bar, hint.height())

    def minimumSizeHint(self) -> QtCore.QSize:
        '''Return the width of the panel and a short height.'''
        return QtCore.QSize(self.sizeHint().width(),
                            super().minimumSizeHint().height())
