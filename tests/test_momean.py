'''Unit tests for MoMean and QMoMean.'''
import unittest
import numpy as np
from qtpy import QtWidgets
from QVideo.filters.momean import MoMean, QMoMean


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_SHAPE = (4, 4)
_A = np.full(_SHAPE, 100, dtype=np.uint8)
_B = np.full(_SHAPE, 200, dtype=np.uint8)


def make_filter(**kwargs) -> MoMean:
    return MoMean(**kwargs)


def make_widget() -> QMoMean:
    return QMoMean(parent=None)


class TestMoMeanAlpha(unittest.TestCase):

    def test_default_alpha(self):
        self.assertAlmostEqual(make_filter().alpha, 0.1)

    def test_custom_alpha(self):
        self.assertAlmostEqual(make_filter(alpha=0.5).alpha, 0.5)

    def test_alpha_clamped_to_one(self):
        self.assertAlmostEqual(make_filter(alpha=2.0).alpha, 1.0)

    def test_alpha_clamped_above_zero(self):
        self.assertGreater(make_filter(alpha=0.0).alpha, 0.0)

    def test_alpha_setter(self):
        f = make_filter()
        f.alpha = 0.3
        self.assertAlmostEqual(f.alpha, 0.3)


class TestMoMeanGet(unittest.TestCase):

    def test_get_returns_none_before_add(self):
        self.assertIsNone(make_filter().get())

    def test_get_returns_ndarray_after_add(self):
        f = make_filter()
        f.add(_A)
        self.assertIsInstance(f.get(), np.ndarray)

    def test_get_returns_uint8(self):
        f = make_filter()
        f.add(_A)
        self.assertEqual(f.get().dtype, np.uint8)

    def test_get_shape_matches_input(self):
        f = make_filter()
        f.add(_A)
        self.assertEqual(f.get().shape, _SHAPE)

    def test_first_frame_is_initial_estimate(self):
        f = make_filter(alpha=0.5)
        f.add(_A)
        np.testing.assert_array_equal(f.get(), _A)


class TestMoMeanAdd(unittest.TestCase):

    def test_add_updates_estimate(self):
        f = make_filter(alpha=0.5)
        f.add(_A)
        f.add(_B)
        result = f.get()
        # After one update: acc = 0.5*200 + 0.5*100 = 150
        np.testing.assert_array_equal(result, np.full(_SHAPE, 150, dtype=np.uint8))

    def test_alpha_one_is_passthrough(self):
        f = make_filter(alpha=1.0)
        f.add(_A)
        f.add(_B)
        np.testing.assert_array_equal(f.get(), _B)

    def test_shape_change_reinitializes(self):
        f = make_filter()
        f.add(_A)
        new_frame = np.full((8, 8), 50, dtype=np.uint8)
        f.add(new_frame)
        self.assertEqual(f.get().shape, (8, 8))

    def test_estimate_converges_toward_new_value(self):
        f = make_filter(alpha=0.5)
        f.add(_A)
        for _ in range(20):
            f.add(_B)
        result = f.get()
        self.assertGreater(int(result[0, 0]), 190)

    def test_does_not_mutate_input(self):
        f = make_filter()
        original = _A.copy()
        f.add(_A)
        np.testing.assert_array_equal(_A, original)


class TestMoMeanReset(unittest.TestCase):

    def test_reset_clears_estimate(self):
        f = make_filter()
        f.add(_A)
        f.reset()
        self.assertIsNone(f.get())

    def test_add_after_reset_reinitializes(self):
        f = make_filter(alpha=0.5)
        f.add(_A)
        f.reset()
        f.add(_B)
        np.testing.assert_array_equal(f.get(), _B)


class TestMoMeanCall(unittest.TestCase):

    def test_call_returns_ndarray(self):
        f = make_filter()
        result = f(_A)
        self.assertIsInstance(result, np.ndarray)

    def test_call_returns_uint8(self):
        f = make_filter()
        result = f(_A)
        self.assertEqual(result.dtype, np.uint8)


class TestQMoMean(unittest.TestCase):

    def test_filter_is_momean(self):
        self.assertIsInstance(make_widget().filter, MoMean)

    def test_title(self):
        self.assertEqual(make_widget().title(), 'Running Mean')

    def test_has_alpha_spinbox(self):
        self.assertTrue(hasattr(make_widget(), '_alphaBox'))

    def test_alpha_spinbox_default(self):
        self.assertAlmostEqual(make_widget()._alphaBox.value(), 0.1)

    def test_set_alpha_updates_filter(self):
        w = make_widget()
        w._setAlpha(0.3)
        self.assertAlmostEqual(w.filter.alpha, 0.3)

    def test_call_when_unchecked_returns_frame_unchanged(self):
        w = make_widget()
        result = w(_A)
        np.testing.assert_array_equal(result, _A)

    def test_call_when_checked_returns_estimate(self):
        w = make_widget()
        w.setChecked(True)
        result = w(_A)
        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(result.dtype, np.uint8)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
