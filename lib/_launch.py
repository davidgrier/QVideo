'''Run a camera application: the startup that every demo shares.'''
import sys
import pyqtgraph as pg
from qtpy import QtGui, QtWidgets
from QVideo.lib.chooser import choose_camera


__all__ = ['launch']


def launch(widget: type[QtWidgets.QWidget],
           title: str | None = None,
           **kwargs) -> None:
    '''Show *widget* for a camera chosen on the command line, and run it.

    The camera backend comes from the command-line flags described in
    :func:`~QVideo.lib.chooser.choose_camera` (a noise camera if there are
    none).  The window closes on Ctrl+Q.  A widget that needs an optional
    package that is not installed ends the program with the error message.

    Parameters
    ----------
    widget : type
        Class of the application window.  It is called with the camera
        tree as its first argument, as :class:`~QVideo.demos.demo.Demo` and
        :class:`~QVideo.QCamcorder.QCamcorder` expect.
    title : str, optional
        Name of the application.
    **kwargs :
        Further keyword arguments for *widget*.

    Examples
    --------
    ::

        from QVideo.lib import launch
        from QVideo.demos import HistogramDemo

        launch(HistogramDemo, 'Histogram Demo')
    '''
    app = pg.mkQApp(title)
    tree = choose_camera().start()
    try:
        window = widget(tree, **kwargs)
    except ImportError as error:
        sys.exit(f'Error: {error}')
    QtWidgets.QShortcut(
        QtGui.QKeySequence('Ctrl+Q'), window).activated.connect(app.quit)
    window.show()
    pg.exec()
