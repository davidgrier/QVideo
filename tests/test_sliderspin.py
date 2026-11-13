'''Unit tests for the 'sliderspin' control of a parameter tree.'''
import unittest

from qtpy import QtWidgets
from pyqtgraph.parametertree import Parameter, ParameterTree

from QVideo.lib import _sliderspin
from QVideo.lib._sliderspin import SliderSpinParameter
from QVideo.widgets.QSliderSpinBox import QSliderSpinBox


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def make(**opts):
    '''Return a ``'sliderspin'`` parameter in a tree that is showing, and
    its control.'''
    entry = dict(name='x', type='sliderspin', value=3., limits=(0., 24.))
    entry.update(opts)
    root = Parameter.create(name='root', type='group', children=[entry])
    tree = ParameterTree(showHeader=False)
    tree.setParameters(root)
    tree.show()
    app.processEvents()
    param = root.child('x')
    item = next(iter(param.items))
    return param, item.widget, item, tree


class TestType(unittest.TestCase):

    def test_the_type_is_registered(self):
        param = Parameter.create(name='x', type='sliderspin', value=1.,
                                 limits=(0., 2.))
        self.assertIsInstance(param, SliderSpinParameter)

    def test_a_real_number_is_a_float(self):
        param, *_ = make()
        param.setValue(3)
        self.assertIsInstance(param.value(), float)

    def test_a_whole_number_is_an_int(self):
        param, *_ = make(value=1280, limits=(16, 1920), **{'int': True})
        self.assertIsInstance(param.value(), int)
        param.setValue(1000.4)
        self.assertEqual(param.value(), 1000)


class TestControl(unittest.TestCase):

    def test_the_control_is_a_slider_with_a_spin_box(self):
        _, widget, *_ = make()
        self.assertIsInstance(widget, QSliderSpinBox)

    def test_the_control_is_there_without_a_click(self):
        # pyqtgraph shows a number as a label until its row is clicked; a
        # slider that waits for a click would be of no use
        _, widget, item, _ = make()
        self.assertFalse(item.hideWidget)
        self.assertTrue(widget.isVisible())
        self.assertTrue(widget.slider.isVisible())

    def test_the_limits_are_the_range(self):
        _, widget, *_ = make(limits=(1e-5, 30.))
        self.assertEqual((widget.minimum, widget.maximum), (1e-5, 30.))
        self.assertTrue(widget.isLogarithmic())

    def test_min_and_max_are_the_range_too(self):
        # the Genicam tree describes its nodes so
        _, widget, *_ = make(limits=None, min=2., max=9.)
        self.assertEqual((widget.minimum, widget.maximum), (2., 9.))

    def test_the_units_are_the_suffix(self):
        _, widget, *_ = make(units='dB')
        self.assertEqual(widget.spin.opts['suffix'], 'dB')

    def test_the_step_of_a_whole_number_is_its_grid(self):
        param, widget, *_ = make(value=1280, limits=(16, 1920), step=16,
                                 **{'int': True})
        self.assertEqual(widget.slider.maximum(), (1920 - 16) // 16)

    def test_log_may_be_given(self):
        _, widget, *_ = make(limits=(1., 50.), log=True)
        self.assertTrue(widget.isLogarithmic())


class TestValue(unittest.TestCase):

    def test_the_slider_sets_the_parameter(self):
        param, widget, *_ = make()
        widget.slider.setValue(500)
        self.assertAlmostEqual(param.value(), 12.)

    def test_every_step_of_a_drag_reaches_the_parameter(self):
        param, widget, *_ = make()
        heard = []
        param.sigValueChanged.connect(lambda p, v: heard.append(v))
        for position in (100, 200, 300):
            widget.slider.setValue(position)
        self.assertEqual(len(heard), 3)

    def test_the_spin_box_sets_the_parameter(self):
        param, widget, *_ = make()
        widget.spin.setValue(18.)
        self.assertEqual(param.value(), 18.)

    def test_the_parameter_moves_the_slider_and_hears_nothing_back(self):
        param, widget, *_ = make()
        heard = []
        param.sigValueChanged.connect(lambda p, v: heard.append(v))
        param.setValue(12.)
        self.assertEqual(heard, [12.])                  # once, not echoed
        self.assertEqual(widget.slider.value(), 500)
        self.assertEqual(widget.value(), 12.)

    def test_a_value_beyond_the_range_ends_in_the_range(self):
        # as for pyqtgraph's own float control: the control clips the value
        # and the parameter follows
        param, widget, *_ = make()
        param.setValue(100.)
        self.assertEqual(param.value(), 24.)
        self.assertEqual(widget.value(), 24.)
        self.assertEqual(widget.slider.value(), widget.slider.maximum())


class TestOptions(unittest.TestCase):

    def test_new_limits_change_the_range(self):
        param, widget, *_ = make()
        param.setLimits((0., 48.))
        self.assertEqual((widget.minimum, widget.maximum), (0., 48.))
        self.assertEqual(widget.value(), 3.)

    def test_a_step_that_is_none_is_ignored(self):
        # the Genicam tree sets step=None for a node without an increment
        param, widget, *_ = make(value=5, limits=(0, 100), step=4,
                                 **{'int': True})
        param.setOpts(step=None)                        # does not raise
        self.assertEqual(widget._step, 4.)

    def test_a_step_is_passed_on(self):
        param, widget, *_ = make(value=5, limits=(0, 100), step=4,
                                 **{'int': True})
        param.setOpts(step=8)
        self.assertEqual(widget._step, 8.)

    def test_units_and_prefixes_are_passed_on(self):
        param, widget, *_ = make()
        param.setOpts(units='ms', siPrefix=True)
        self.assertEqual(widget.spin.opts['suffix'], 'ms')
        self.assertTrue(widget.spin.opts['siPrefix'])

    def test_the_scale_may_be_changed(self):
        param, widget, *_ = make(limits=(1., 50.))
        self.assertFalse(widget.isLogarithmic())
        param.setOpts(log=True)
        self.assertTrue(widget.isLogarithmic())

    def test_min_and_max_may_be_changed(self):
        param, widget, *_ = make(limits=None, min=2., max=9.)
        param.setOpts(min=1., max=12.)
        self.assertEqual((widget.minimum, widget.maximum), (1., 12.))

    def test_disabling_the_parameter_disables_the_control(self):
        param, widget, *_ = make()
        param.setOpts(enabled=False)
        self.assertFalse(widget.slider.isEnabled())
        self.assertFalse(widget.spin.isEnabled())
        param.setOpts(enabled=True)
        self.assertTrue(widget.slider.isEnabled())

    def test_a_read_only_parameter_locks_the_control(self):
        param, widget, *_ = make()
        param.setOpts(readonly=True)
        self.assertFalse(widget.slider.isEnabled())
        self.assertTrue(widget.spin.isReadOnly())


class TestModule(unittest.TestCase):

    def test_the_module_says_what_it_offers(self):
        self.assertEqual(sorted(_sliderspin.__all__),
                         ['SliderSpinParameter', 'SliderSpinParameterItem'])

    def test_importing_the_module_does_not_import_the_widgets(self):
        import subprocess
        import sys
        code = ('import sys; import QVideo.lib._sliderspin; '
                'sys.exit(int("QVideo.widgets" in sys.modules))')
        result = subprocess.run([sys.executable, '-c', code],
                                capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode())


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
