'''Unit tests for QSliderSpinBox.'''
import math
import unittest

from qtpy import QtWidgets

from QVideo.tests.signals import record
from QVideo.widgets.QSliderSpinBox import QSliderSpinBox


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def exposure(**kwargs):
    '''Six and a half decades of exposure time, in seconds.'''
    return QSliderSpinBox(minimum=1e-5, maximum=30., value=0.01, **kwargs)


class TestLinear(unittest.TestCase):

    def setUp(self):
        self.w = QSliderSpinBox(minimum=0., maximum=24., value=3.)

    def test_the_value_is_shown_in_both(self):
        self.assertEqual(self.w.value(), 3.)
        self.assertEqual(self.w.slider.value(), 125)         # 3/24 of 1000

    def test_the_ends_of_the_slider_are_the_ends_of_the_range(self):
        self.w.slider.setValue(0)
        self.assertEqual(self.w.value(), 0.)
        self.w.slider.setValue(self.w.slider.maximum())
        self.assertEqual(self.w.value(), 24.)

    def test_the_slider_is_linear(self):
        self.w.slider.setValue(500)
        self.assertAlmostEqual(self.w.value(), 12.)

    def test_a_range_of_two_decades_or_less_is_linear(self):
        self.assertFalse(QSliderSpinBox(minimum=1., maximum=100.)
                         .isLogarithmic())

    def test_a_range_that_includes_zero_is_linear(self):
        self.assertFalse(QSliderSpinBox(minimum=0., maximum=1e6)
                         .isLogarithmic())


class TestLogarithmic(unittest.TestCase):

    def test_a_positive_range_of_many_decades_is_logarithmic(self):
        self.assertTrue(exposure().isLogarithmic())

    def test_the_middle_is_the_geometric_mean(self):
        w = exposure()
        w.slider.setValue(500)
        self.assertAlmostEqual(w.value(), math.sqrt(1e-5 * 30.), places=6)

    def test_the_value_goes_to_the_slider_and_back(self):
        w = exposure()
        for value in (2e-5, 1e-3, 0.01, 0.5, 20.):
            w.setValue(value)
            w.slider.setValue(w.slider.value())      # as if it were moved
            self.assertAlmostEqual(w.value() / value, 1., delta=0.015)

    def test_it_may_be_turned_off(self):
        self.assertFalse(exposure(log=False).isLogarithmic())

    def test_it_may_be_asked_for_a_range_of_two_decades(self):
        self.assertTrue(QSliderSpinBox(minimum=1., maximum=50., log=True)
                        .isLogarithmic())

    def test_a_range_that_includes_zero_cannot_be_logarithmic(self):
        self.assertFalse(QSliderSpinBox(minimum=0., maximum=1e6, log=True)
                         .isLogarithmic())

    def test_the_scale_may_change_and_the_value_stays(self):
        w = exposure()
        w.setLogarithmic(False)
        self.assertEqual(w.value(), 0.01)
        self.assertAlmostEqual(w.slider.value() / 1000, 0.01 / 30., places=3)
        w.setLogarithmic(None)
        self.assertTrue(w.isLogarithmic())
        self.assertEqual(w.value(), 0.01)


class TestWholeNumbers(unittest.TestCase):

    def setUp(self):
        self.w = QSliderSpinBox(minimum=16, maximum=1920, integer=True,
                                step=16, value=1280)

    def test_the_value_is_an_int(self):
        self.assertIsInstance(self.w.value(), int)
        self.assertEqual(self.w.value(), 1280)

    def test_a_range_of_whole_numbers_is_linear_even_if_it_spans_decades(self):
        self.assertFalse(self.w.isLogarithmic())          # 16 to 1920

    def test_the_slider_has_a_notch_for_each_step(self):
        self.assertEqual(self.w.slider.maximum(), (1920 - 16) // 16)

    def test_the_slider_moves_on_the_grid(self):
        self.w.slider.setValue(3)
        self.assertEqual(self.w.value(), 16 + 3 * 16)

    def test_the_ends_are_the_ends_of_the_range(self):
        self.w.slider.setValue(0)
        self.assertEqual(self.w.value(), 16)
        self.w.slider.setValue(self.w.slider.maximum())
        self.assertEqual(self.w.value(), 1920)

    def test_a_short_range_has_a_notch_for_each_number(self):
        w = QSliderSpinBox(minimum=0, maximum=10, integer=True, value=4)
        self.assertEqual(w.slider.maximum(), 10)
        w.slider.setValue(7)
        self.assertEqual(w.value(), 7)

    def test_a_long_range_has_a_thousand_positions(self):
        w = QSliderSpinBox(minimum=0, maximum=10_000_000, integer=True,
                           value=5)
        self.assertEqual(w.slider.maximum(), 1000)
        w.slider.setValue(500)
        self.assertEqual(w.value(), 5_000_000)

    def test_whole_numbers_may_be_logarithmic_when_asked(self):
        w = QSliderSpinBox(minimum=10, maximum=1_000_000, integer=True,
                           log=True, value=1000)
        self.assertTrue(w.isLogarithmic())
        w.slider.setValue(500)
        self.assertEqual(w.value(), 3162)                # 10 * 1e5 ** 0.5


class TestSignals(unittest.TestCase):

    def setUp(self):
        self.w = QSliderSpinBox(minimum=0., maximum=24., value=3.)
        self.heard = record(self.w.valueChanged)

    def test_dragging_the_slider_is_heard_at_every_step(self):
        for position in (200, 300, 400):
            self.w.slider.setValue(position)
        for (value,), expected in zip(self.heard, (4.8, 7.2, 9.6)):
            self.assertAlmostEqual(value, expected)
        self.assertEqual(len(self.heard), 3)

    def test_the_spin_box_follows_the_slider(self):
        self.w.slider.setValue(500)
        self.assertAlmostEqual(self.w.spin.value(), 12.)

    def test_typing_in_the_spin_box_is_heard_and_moves_the_slider(self):
        self.w.spin.setValue(18.)
        self.assertEqual(self.heard, [(18.,)])
        self.assertEqual(self.w.slider.value(), 750)

    def test_set_value_says_nothing(self):
        self.w.setValue(10.)
        self.assertEqual(self.heard, [])
        self.assertEqual(self.w.value(), 10.)
        self.assertEqual(self.w.slider.value(), round(1000 * 10 / 24))

    def test_set_range_says_nothing(self):
        self.w.setRange(0., 48.)
        self.assertEqual(self.heard, [])

    def test_a_value_beyond_the_range_is_brought_in(self):
        self.w.setValue(100.)
        self.assertEqual(self.w.value(), 24.)
        self.assertEqual(self.w.slider.value(), self.w.slider.maximum())
        self.assertEqual(self.heard, [])


class TestRange(unittest.TestCase):

    def test_the_value_stays_when_the_range_changes(self):
        w = QSliderSpinBox(minimum=0., maximum=24., value=3.)
        w.setRange(0., 48.)
        self.assertEqual(w.value(), 3.)
        self.assertEqual(w.slider.value(), round(1000 * 3 / 48))
        self.assertEqual((w.minimum, w.maximum), (0., 48.))

    def test_a_value_outside_the_new_range_is_brought_in(self):
        w = QSliderSpinBox(minimum=0., maximum=24., value=20.)
        w.setRange(0., 10.)
        self.assertEqual(w.value(), 10.)

    def test_the_same_range_changes_nothing(self):
        w = QSliderSpinBox(minimum=0., maximum=24., value=3.)
        position = w.slider.value()
        w.setRange(0., 24.)
        self.assertEqual(w.slider.value(), position)

    def test_a_whole_range_gets_its_notches_again(self):
        w = QSliderSpinBox(minimum=0, maximum=10, integer=True, value=4)
        w.setRange(0, 100)
        self.assertEqual(w.slider.maximum(), 100)
        self.assertEqual(w.value(), 4)

    def test_a_range_of_one_point_has_no_slider(self):
        w = QSliderSpinBox(minimum=5., maximum=5., value=5.)
        self.assertFalse(w.slider.isEnabled())

    def test_the_slider_is_back_when_the_range_opens(self):
        w = QSliderSpinBox(minimum=5., maximum=5., value=5.)
        w.setRange(0., 10.)
        self.assertTrue(w.slider.isEnabled())


class TestAccess(unittest.TestCase):

    def test_read_only_locks_both(self):
        w = QSliderSpinBox(minimum=0., maximum=24., value=3.)
        w.setReadOnly(True)
        self.assertFalse(w.slider.isEnabled())
        self.assertTrue(w.spin.isReadOnly())
        w.setReadOnly(False)
        self.assertTrue(w.slider.isEnabled())
        self.assertFalse(w.spin.isReadOnly())

    def test_disabling_the_widget_disables_both(self):
        w = QSliderSpinBox(minimum=0., maximum=24., value=3.)
        w.setEnabled(False)
        self.assertFalse(w.slider.isEnabled())
        self.assertFalse(w.spin.isEnabled())

    def test_options_go_to_the_spin_box(self):
        w = QSliderSpinBox(minimum=0., maximum=24., value=3.)
        w.setOpts(suffix='dB')
        self.assertEqual(w.spin.opts['suffix'], 'dB')

    def test_a_new_step_is_the_grid_of_whole_numbers(self):
        w = QSliderSpinBox(minimum=0, maximum=160, integer=True, step=1,
                           value=0)
        w.setOpts(step=16)
        w.slider.setValue(w.slider.maximum())
        self.assertEqual(w.value(), 160)

    def test_the_spin_box_of_a_tree_can_be_selected(self):
        w = QSliderSpinBox(minimum=0., maximum=24., value=3.)
        self.assertIsInstance(w.lineEdit(), QtWidgets.QLineEdit)
        w.selectNumber()                                  # does not raise


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
