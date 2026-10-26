'''A filter rack that runs its filters on a worker thread.'''
from qtpy import QtWidgets
from QVideo.lib.QFilterRackWidget import QFilterRackWidget
from QVideo.lib.QFilterPipeline import QFilterPipeline


__all__ = ['QFilterRack']


class QFilterRack(QFilterRackWidget):

    '''A :class:`~QVideo.lib.QFilterRackWidget.QFilterRackWidget` that
    filters a live source.

    The rack owns a :class:`~QVideo.lib.QFilterPipeline.QFilterPipeline`
    that follows the rack: it runs the switched-on filters, in order, on
    a worker thread, so a slow filter never stalls the interface or the
    camera, and it keeps the newest frame when it falls behind.
    Connect consumers to :attr:`pipeline`, not to the raw source, so
    that they share one filtered stream::

        rack = QFilterRack(source=camera)
        screen.source = rack.pipeline

    The pipeline stops when the application quits and when the rack is
    deleted, so a rack needs no explicit shutdown.  Closing a window only
    hides the rack: call ``rack.pipeline.stop()`` to stop it sooner.

    Use :class:`~QVideo.lib.QFilterRackWidget.QFilterRackWidget` to
    apply the filters to recorded frames, or to design a pipeline,
    without a thread.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget.  Default: ``None``.
    editable : bool
        If ``False``, the toolbar, drag handles, and close buttons are
        all hidden.  Default: ``True``.
    source : QVideoSource or None
        Provider of the frames to filter.  It can be set later.
        Default: ``None``.
    depth : int
        Frames the pipeline may queue while its filters are busy.
        Default: ``1``, which always processes the newest.
    '''

    def __init__(self,
                 parent: QtWidgets.QWidget | None = None,
                 editable: bool = True,
                 source=None,
                 depth: int = 1) -> None:
        super().__init__(parent, editable)
        self.pipeline = QFilterPipeline(source, rack=self, depth=depth)
        self.destroyed.connect(self.pipeline.stop)

    @property
    def source(self):
        '''The source whose frames are filtered.'''
        return self.pipeline.source

    @source.setter
    def source(self, source) -> None:
        self.pipeline.source = source


if __name__ == '__main__':  # pragma: no cover
    QFilterRack.example()
