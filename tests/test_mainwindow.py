'''Every application must work as the center of a QMainWindow.

Real applications embed QVideo components in a main window, so each demo is
shown that way here, with a video shape that fits the screen and one that
does not, before and after the user resizes the window.
'''
import contextlib
import importlib
import unittest
from qtpy import QtCore, QtWidgets
from QVideo.cameras.Noise._tree import QNoiseTree
from QVideo.demos.demo import Demo
from QVideo.lib import QCameraTree


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

APPLICATIONS = [('QVideo.QCamcorder', 'QCamcorder', {}),
                ('QVideo.demos.demo', 'Demo', {}),
                ('QVideo.demos.filterdemo', 'FilterDemo',
                 {'filters': ['Smoothing']}),
                ('QVideo.demos.filterrackdemo', 'FilterRackDemo', {}),
                ('QVideo.demos.ROIdemo', 'ROIDemo', {}),
                ('QVideo.demos.histogramdemo', 'HistogramDemo', {}),
                ('QVideo.demos.uniformitydemo', 'UniformityDemo', {}),
                ('QVideo.demos.circulardemo', 'CircularDemo', {}),
                ('QVideo.demos.compositedemo', 'CompositeDemo', {}),
                ('QVideo.demos.combineddemo', 'CombinedDemo', {})]
SHAPES = [QtCore.QSize(320, 240), QtCore.QSize(640, 480),
          QtCore.QSize(1920, 1080), QtCore.QSize(4096, 3000)]


def settle() -> None:
    for _ in range(5):
        app.processEvents()


@contextlib.contextmanager
def shown(name, cls, kwargs):
    '''Show an application as the center of a main window.

    It ends as an application does: quit, which stops every thread,
    and then Qt deletes the window.
    '''
    tree = QNoiseTree()
    central = getattr(importlib.import_module(name), cls)(tree, **kwargs)
    window = QtWidgets.QMainWindow()
    window.setCentralWidget(central)
    window.statusBar()
    window.show()
    settle()
    try:
        yield window, central
    finally:
        window.close()
        tree.stop()
        app.aboutToQuit.emit()
        window.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


class TestInMainWindow(unittest.TestCase):

    def covers(self, central, shape):
        '''Whether the view shows the whole frame.'''
        x, y = central.screen.view.viewRange()
        return (x[0] <= 0 and x[1] >= shape.width()
                and y[0] <= 0 and y[1] >= shape.height())

    def test_the_window_fits_the_screen_and_shows_the_whole_frame(self):
        available = app.primaryScreen().availableGeometry()
        for name, cls, kwargs in APPLICATIONS:
            for shape in SHAPES:
                with self.subTest(application=cls, shape=shape):
                    with shown(name, cls, kwargs) as (window, central):
                        central.screen.updateShape(shape)
                        settle()
                        # no larger than the screen, unless the controls
                        # need it (the style sets how much that is)
                        least = window.minimumSizeHint().expandedTo(
                            window.minimumSize())
                        info = (f'size {window.size()}, '
                                f'sizeHint {window.sizeHint()}, '
                                f'minimumSizeHint {window.minimumSizeHint()}, '
                                f'minimumSize {window.minimumSize()}, '
                                f'screen {available.size()}')
                        self.assertLessEqual(window.width(), max(
                            available.width(), least.width()), info)
                        self.assertLessEqual(window.height(), max(
                            available.height(), least.height()), info)
                        self.assertTrue(self.covers(central, shape))

    def test_the_whole_frame_stays_in_view_when_the_window_is_resized(self):
        shape = QtCore.QSize(640, 480)
        for name, cls, kwargs in APPLICATIONS:
            with self.subTest(application=cls):
                with shown(name, cls, kwargs) as (window, central):
                    central.screen.updateShape(shape)
                    settle()
                    for dw, dh in ((100, 40), (-60, -30), (0, 80)):
                        window.resize(window.width() + dw,
                                      window.height() + dh)
                        settle()
                        self.assertTrue(self.covers(central, shape))


class TestCompactControls(unittest.TestCase):
    '''The control column asks for no more height than its contents need,
    so that the video, not the controls, sets the size of the window.'''

    def test_the_camera_tree_gives_up_height_to_its_neighbors(self):
        tree = QNoiseTree()
        self.addCleanup(tree.stop)
        policy = tree.sizePolicy().verticalPolicy()
        self.assertEqual(policy, QtWidgets.QSizePolicy.Policy.Expanding)
        self.assertEqual(tree.sizeHint().height(), tree.minimumHeight())

    def test_the_controls_ask_for_the_least_height_of_the_tree(self):
        for name, cls, kwargs in APPLICATIONS:
            with self.subTest(application=cls):
                with shown(name, cls, kwargs) as (window, central):
                    if not hasattr(central, 'controls'):
                        continue  # the demos built on Demo have no panel
                    layout = central.controls.layout()
                    widgets = [layout.itemAt(i).widget()
                               for i in range(layout.count())]
                    hints = [w.minimumHeight()
                             if isinstance(w, QCameraTree)
                             else w.sizeHint().height() for w in widgets]
                    margins = layout.contentsMargins()
                    needed = (sum(hints) + margins.top() + margins.bottom()
                              + layout.spacing() * (len(widgets) - 1))
                    self.assertTrue(any(isinstance(w, QCameraTree)
                                        for w in widgets))
                    self.assertLessEqual(
                        central.controls.sizeHint().height(), needed)

    def test_the_controls_do_not_overlap(self):
        for name, cls, kwargs in APPLICATIONS:
            for shape in SHAPES:
                with self.subTest(application=cls, shape=shape):
                    with shown(name, cls, kwargs) as (window, central):
                        if not hasattr(central, 'controls'):
                            continue
                        central.screen.updateShape(shape)
                        settle()
                        layout = central.controls.layout()
                        widgets = [layout.itemAt(i).widget()
                                   for i in range(layout.count())]
                        for above, below in zip(widgets, widgets[1:]):
                            self.assertLess(above.geometry().bottom(),
                                            below.geometry().top())


class TestFirstShow(unittest.TestCase):
    '''The shape of the video is known before the screen has a window.'''

    SHAPE = QtCore.QSize(640, 360)

    @contextlib.contextmanager
    def embedded(self, size=None):
        '''A demo that knows its video shape, in a main window not yet
        shown, which ends as an application does.'''
        tree = QNoiseTree()
        demo = Demo(tree)
        demo.screen.updateShape(self.SHAPE)  # as a camera that opened
        window = QtWidgets.QMainWindow()
        window.setCentralWidget(demo)
        if size is not None:
            window.resize(*size)
        try:
            yield window, demo
        finally:
            window.close()
            tree.stop()
            app.aboutToQuit.emit()
            window.deleteLater()
            app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)

    def test_the_window_is_fitted_to_the_video_when_shown(self):
        with self.embedded() as (window, demo):
            window.show()
            settle()
            screen = demo.screen
            self.assertAlmostEqual(screen.width() / screen.height(),
                                   self.SHAPE.width() / self.SHAPE.height(),
                                   delta=0.03)

    def test_a_window_that_was_sized_is_left_alone(self):
        with self.embedded(size=(1000, 700)) as (window, demo):
            window.show()
            settle()
            self.assertEqual((window.width(), window.height()), (1000, 700))

    def test_showing_the_screen_again_does_not_resize_the_window(self):
        with self.embedded() as (window, demo):
            window.show()
            settle()
            window.resize(1100, 650)
            demo.screen.hide()
            demo.screen.show()
            settle()
            self.assertEqual((window.width(), window.height()), (1100, 650))


if __name__ == '__main__':
    unittest.main()
