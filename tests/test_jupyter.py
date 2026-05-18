'''Unit tests for lib/_jupyter.py.'''
import importlib.util
import unittest
from unittest.mock import MagicMock, patch
from qtpy import QtWidgets

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_HAS_IPYWIDGETS = importlib.util.find_spec('ipywidgets') is not None


@unittest.skipUnless(_HAS_IPYWIDGETS, 'ipywidgets not installed')
class TestCameraControls(unittest.TestCase):

    def setUp(self):
        from QVideo.lib._jupyter import CameraControls
        self.CameraControls = CameraControls
        self.float_setter = MagicMock()
        self.int_setter   = MagicMock()
        self.bool_setter  = MagicMock()
        self.str_setter   = MagicMock()

        self.camera = MagicMock()
        self.camera.name = 'TestCamera'
        self.camera._properties = {
            'fps': {
                'getter': lambda: 30.0,
                'setter': self.float_setter,
                'ptype': float,
                'minimum': 1.0,
                'maximum': 120.0,
            },
            'gain': {
                'getter': lambda: 1.0,
                'setter': self.float_setter,
                'ptype': float,
            },
            'width': {
                'getter': lambda: 640,
                'setter': None,
                'ptype': int,
            },
            'frames': {
                'getter': lambda: 10,
                'setter': self.int_setter,
                'ptype': int,
                'minimum': 1,
                'maximum': 100,
            },
            'color': {
                'getter': lambda: True,
                'setter': self.bool_setter,
                'ptype': bool,
            },
            'mode': {
                'getter': lambda: 'fast',
                'setter': self.str_setter,
                'ptype': str,
                'limits': ['fast', 'slow', 'burst'],
            },
            'label': {
                'getter': lambda: 'test',
                'setter': self.str_setter,
                'ptype': str,
            },
        }

    def _make(self):
        return self.CameraControls(self.camera)

    # ------------------------------------------------------------------
    # Widget creation
    # ------------------------------------------------------------------

    def test_creates_float_slider_when_bounded(self):
        import ipywidgets as widgets
        ctrl = self._make()
        self.assertIsInstance(ctrl._widgets['fps'], widgets.FloatSlider)

    def test_creates_float_text_when_unbounded(self):
        import ipywidgets as widgets
        ctrl = self._make()
        self.assertIsInstance(ctrl._widgets['gain'], widgets.FloatText)

    def test_creates_int_slider_when_bounded(self):
        import ipywidgets as widgets
        ctrl = self._make()
        self.assertIsInstance(ctrl._widgets['frames'], widgets.IntSlider)

    def test_creates_int_text_when_unbounded(self):
        import ipywidgets as widgets
        ctrl = self._make()
        # width has no min/max
        self.assertIsInstance(ctrl._widgets['width'], widgets.IntText)

    def test_creates_checkbox_for_bool(self):
        import ipywidgets as widgets
        ctrl = self._make()
        self.assertIsInstance(ctrl._widgets['color'], widgets.Checkbox)

    def test_creates_dropdown_for_str_with_limits(self):
        import ipywidgets as widgets
        ctrl = self._make()
        self.assertIsInstance(ctrl._widgets['mode'], widgets.Dropdown)

    def test_creates_text_for_str_without_limits(self):
        import ipywidgets as widgets
        ctrl = self._make()
        self.assertIsInstance(ctrl._widgets['label'], widgets.Text)

    def test_widget_count_matches_properties(self):
        ctrl = self._make()
        self.assertEqual(len(ctrl._widgets), len(self.camera._properties))

    # ------------------------------------------------------------------
    # Initial values
    # ------------------------------------------------------------------

    def test_initial_float_value(self):
        ctrl = self._make()
        self.assertAlmostEqual(ctrl._widgets['fps'].value, 30.0)

    def test_initial_int_value(self):
        ctrl = self._make()
        self.assertEqual(ctrl._widgets['width'].value, 640)

    def test_initial_bool_value(self):
        ctrl = self._make()
        self.assertTrue(ctrl._widgets['color'].value)

    def test_initial_str_value(self):
        ctrl = self._make()
        self.assertEqual(ctrl._widgets['mode'].value, 'fast')

    # ------------------------------------------------------------------
    # Read-only
    # ------------------------------------------------------------------

    def test_readonly_widget_is_disabled(self):
        ctrl = self._make()
        self.assertTrue(ctrl._widgets['width'].disabled)

    def test_writable_widget_is_enabled(self):
        ctrl = self._make()
        self.assertFalse(ctrl._widgets['fps'].disabled)

    # ------------------------------------------------------------------
    # Setter calls
    # ------------------------------------------------------------------

    def test_changing_float_widget_calls_setter(self):
        ctrl = self._make()
        ctrl._widgets['fps'].value = 60.0
        self.float_setter.assert_called_with(60.0)

    def test_changing_bool_widget_calls_setter(self):
        ctrl = self._make()
        ctrl._widgets['color'].value = False
        self.bool_setter.assert_called_with(False)

    def test_changing_int_widget_calls_setter(self):
        ctrl = self._make()
        ctrl._widgets['frames'].value = 50
        self.int_setter.assert_called_with(50)

    def test_changing_readonly_widget_does_not_call_setter(self):
        setter = MagicMock()
        ctrl = self._make()
        # width is read-only; no setter should be registered
        ctrl._widgets['width'].value = 1280
        setter.assert_not_called()

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def test_refresh_updates_widget_values(self):
        ctrl = self._make()
        self.camera._properties['fps']['getter'] = lambda: 90.0
        ctrl.refresh()
        self.assertAlmostEqual(ctrl._widgets['fps'].value, 90.0)

    def test_refresh_does_not_trigger_setters(self):
        ctrl = self._make()
        self.camera._properties['fps']['getter'] = lambda: 90.0
        ctrl.refresh()
        self.float_setter.assert_not_called()

    def test_refresh_handles_none_getter(self):
        ctrl = self._make()
        self.camera._properties['fps']['getter'] = lambda: None
        ctrl.refresh()  # should not raise

    # ------------------------------------------------------------------
    # CameraProxy integration
    # ------------------------------------------------------------------

    def test_proxy_controls_returns_camera_controls(self):
        from QVideo.lib._camera import Camera
        from QVideo.lib._jupyter import CameraControls
        cam = MagicMock()
        cam.isOpen.return_value = True
        cam._properties = self.camera._properties
        cam.name = 'Noise'
        with patch('QVideo.lib._camera._open', return_value=cam):
            proxy = Camera('noise')
            ctrl = proxy.controls()
        self.assertIsInstance(ctrl, CameraControls)

    def test_proxy_controls_raises_without_ipywidgets(self):
        from QVideo.lib._camera import Camera
        cam = MagicMock()
        cam.isOpen.return_value = True
        cam._properties = {}
        with patch('QVideo.lib._camera._open', return_value=cam):
            proxy = Camera('noise')
        with patch.dict('sys.modules', {'QVideo.lib._jupyter': None}):
            with self.assertRaises(ImportError):
                proxy.controls()


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
