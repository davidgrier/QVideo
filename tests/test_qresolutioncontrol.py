'''Unit tests for QResolutionControl.'''
import unittest
import numpy as np
from pyqtgraph.Qt import QtCore, QtWidgets, QtTest
from QVideo.lib.QResolutionControl import QResolutionControl


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

_FRAME = np.zeros((480, 640, 3), dtype=np.uint8)
_RESOLUTIONS = [(640, 480), (1280, 720), (1920, 1080)]


# ---------------------------------------------------------------------------
# Minimal fakes
# ---------------------------------------------------------------------------

class FakeCamera(QtCore.QObject):
    '''In-memory camera with mutable width/height/fps state.'''

    shapeChanged = QtCore.pyqtSignal(QtCore.QSize)

    def __init__(self, width=640, height=480, fps=30.):
        super().__init__()
        self._state = {'width': width, 'height': height, 'fps': fps}
        self._properties = {
            'width':  {'getter': lambda: int(self._state['width']),
                       'setter': lambda v: self._state.__setitem__('width', int(v)),
                       'ptype': int},
            'height': {'getter': lambda: int(self._state['height']),
                       'setter': lambda v: self._state.__setitem__('height', int(v)),
                       'ptype': int},
            'fps':    {'getter': lambda: float(self._state['fps']),
                       'setter': lambda v: self._state.__setitem__('fps', float(v)),
                       'ptype': float},
        }

    def get(self, name):
        return self._properties[name]['getter']()

    def set(self, name, value):
        spec = self._properties.get(name)
        if spec and spec.get('setter'):
            spec['setter'](value)


class FakeCameraNoFps(FakeCamera):
    '''Camera without an fps property.'''

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        del self._properties['fps']


class FakeCameraReadOnly(FakeCamera):
    '''Camera with read-only width and height.'''

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._properties['width']['setter'] = None
        self._properties['height']['setter'] = None


class FakeSource(QtCore.QObject):
    '''Minimal QVideoSource stand-in with a real newFrame signal.'''

    newFrame = QtCore.pyqtSignal(np.ndarray)

    def __init__(self, camera=None):
        super().__init__()
        self.source = camera or FakeCamera()
        self._running = False

    def isRunning(self):
        return self._running

    def stop(self):
        self._running = False

    def wait(self):
        pass

    def start(self):
        self._running = True


def make_control(camera=None, resolutions=None):
    src = FakeSource(camera or FakeCamera())
    ctrl = QResolutionControl(src, resolutions=resolutions)
    return ctrl, src, src.source


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestInit(unittest.TestCase):

    def test_source_property(self):
        ctrl, src, _ = make_control()
        self.assertIs(ctrl.source, src)

    def test_camera_property(self):
        ctrl, src, cam = make_control()
        self.assertIs(ctrl.camera, cam)

    def test_width_spin_initialized_from_camera(self):
        ctrl, _, _ = make_control(FakeCamera(width=1280))
        self.assertEqual(ctrl._widthSpin.value(), 1280)

    def test_height_spin_initialized_from_camera(self):
        ctrl, _, _ = make_control(FakeCamera(height=720))
        self.assertEqual(ctrl._heightSpin.value(), 720)

    def test_fps_spin_initialized_from_camera(self):
        ctrl, _, _ = make_control(FakeCamera(fps=15.))
        self.assertAlmostEqual(ctrl._fpsSpin.value(), 15.)

    def test_fps_spin_absent_when_camera_has_no_fps(self):
        ctrl, _, _ = make_control(FakeCameraNoFps())
        self.assertIsNone(ctrl._fpsSpin)

    def test_result_label_shows_fps(self):
        ctrl, _, _ = make_control(FakeCamera(fps=30.))
        self.assertIn('30.0', ctrl._resultLabel.text())

    def test_result_label_empty_when_no_fps(self):
        ctrl, _, _ = make_control(FakeCameraNoFps())
        self.assertEqual(ctrl._resultLabel.text(), '')

    def test_no_dropdown_when_no_resolutions(self):
        ctrl, _, _ = make_control(resolutions=None)
        self.assertIsNone(ctrl._resolutionCombo)

    def test_dropdown_created_when_resolutions_given(self):
        ctrl, _, _ = make_control(resolutions=_RESOLUTIONS)
        self.assertIsNotNone(ctrl._resolutionCombo)

    def test_dropdown_entry_count(self):
        ctrl, _, _ = make_control(resolutions=_RESOLUTIONS)
        self.assertEqual(ctrl._resolutionCombo.count(), len(_RESOLUTIONS))

    def test_dropdown_matches_initial_resolution(self):
        ctrl, _, _ = make_control(FakeCamera(width=640, height=480),
                                  resolutions=_RESOLUTIONS)
        self.assertEqual(ctrl._resolutionCombo.currentText(), '640\u00d7480')

    def test_dropdown_index_minus_one_when_no_match(self):
        ctrl, _, _ = make_control(FakeCamera(width=800, height=600),
                                  resolutions=_RESOLUTIONS)
        self.assertEqual(ctrl._resolutionCombo.currentIndex(), -1)


class TestDropdownSpinboxSync(unittest.TestCase):

    def setUp(self):
        self.ctrl, _, _ = make_control(FakeCamera(width=640, height=480),
                                       resolutions=_RESOLUTIONS)

    def test_selecting_dropdown_updates_width_spin(self):
        self.ctrl._resolutionCombo.setCurrentText('1280\u00d7720')
        self.assertEqual(self.ctrl._widthSpin.value(), 1280)

    def test_selecting_dropdown_updates_height_spin(self):
        self.ctrl._resolutionCombo.setCurrentText('1280\u00d7720')
        self.assertEqual(self.ctrl._heightSpin.value(), 720)

    def test_editing_spin_to_listed_value_selects_dropdown(self):
        self.ctrl._widthSpin.setValue(1280)
        self.ctrl._heightSpin.setValue(720)
        self.assertEqual(self.ctrl._resolutionCombo.currentText(), '1280\u00d7720')

    def test_editing_spin_to_unlisted_value_clears_dropdown(self):
        self.ctrl._widthSpin.setValue(800)
        self.assertEqual(self.ctrl._resolutionCombo.currentIndex(), -1)

    def test_dropdown_change_does_not_retrigger_spin_signals(self):
        '''Selecting from the dropdown must not cause a spin→dropdown loop.'''
        call_count = []
        self.ctrl._widthSpin.valueChanged.connect(
            lambda v: call_count.append(v))
        self.ctrl._resolutionCombo.setCurrentText('1920\u00d71080')
        # valueChanged fires once (from blockSignals-free setValue), that's fine
        self.assertLessEqual(len(call_count), 1)


class TestIsWritable(unittest.TestCase):

    def test_writable_property_returns_true(self):
        ctrl, _, _ = make_control()
        self.assertTrue(ctrl._isWritable('width'))

    def test_readonly_property_returns_false(self):
        ctrl, _, _ = make_control(FakeCameraReadOnly())
        self.assertFalse(ctrl._isWritable('width'))
        self.assertFalse(ctrl._isWritable('height'))

    def test_missing_property_returns_false(self):
        ctrl, _, _ = make_control()
        self.assertFalse(ctrl._isWritable('nonexistent'))


class TestApplyNotRunning(unittest.TestCase):
    '''apply() when source is not running: sets props, no stop/start.'''

    def setUp(self):
        self.ctrl, self.src, self.cam = make_control()
        self.src._running = False

    def test_sets_width_on_camera(self):
        self.ctrl._widthSpin.setValue(1280)
        self.ctrl._heightSpin.setValue(720)
        self.ctrl.apply()
        self.assertEqual(self.cam.get('width'), 1280)

    def test_sets_height_on_camera(self):
        self.ctrl._widthSpin.setValue(1280)
        self.ctrl._heightSpin.setValue(720)
        self.ctrl.apply()
        self.assertEqual(self.cam.get('height'), 720)

    def test_sets_fps_on_camera(self):
        self.ctrl._fpsSpin.setValue(15.)
        self.ctrl.apply()
        self.assertAlmostEqual(self.cam.get('fps'), 15.)

    def test_source_not_started(self):
        self.ctrl.apply()
        self.assertFalse(self.src.isRunning())

    def test_controls_re_enabled_after_apply(self):
        self.ctrl.apply()
        self.assertTrue(self.ctrl._applyBtn.isEnabled())
        self.assertTrue(self.ctrl._widthSpin.isEnabled())


class TestApplyRunning(unittest.TestCase):
    '''apply() when source is running: stops, sets props, restarts.'''

    def setUp(self):
        self.ctrl, self.src, self.cam = make_control()
        self.src._running = True
        self.stopped = []
        self.started = []
        self.src.stop = lambda: (self.stopped.append(True),
                                  setattr(self.src, '_running', False))
        self.src.start = lambda: self.started.append(True)

    def test_source_stopped(self):
        self.ctrl.apply()
        self.assertEqual(len(self.stopped), 1)

    def test_source_restarted(self):
        self.ctrl.apply()
        self.assertEqual(len(self.started), 1)

    def test_width_set_on_camera(self):
        self.ctrl._widthSpin.setValue(1280)
        self.ctrl._heightSpin.setValue(720)
        self.ctrl.apply()
        self.assertEqual(self.cam.get('width'), 1280)

    def test_controls_disabled_during_restart(self):
        '''Controls must be disabled before start() is called.'''
        enabled_at_start = []
        self.src.start = lambda: enabled_at_start.append(
            self.ctrl._applyBtn.isEnabled())
        self.ctrl.apply()
        self.assertFalse(enabled_at_start[0])

    def test_controls_still_disabled_before_first_frame(self):
        self.ctrl.apply()
        self.assertFalse(self.ctrl._applyBtn.isEnabled())

    def test_readonly_width_not_set(self):
        ctrl, src, cam = make_control(FakeCameraReadOnly())
        src._running = True
        original = cam.get('width')
        ctrl._widthSpin.setValue(1280)
        ctrl.apply()
        self.assertEqual(cam.get('width'), original)


class TestApplyReadOnly(unittest.TestCase):
    '''apply() skips set() for read-only properties.'''

    def test_does_not_call_set_on_readonly_width(self):
        ctrl, src, cam = make_control(FakeCameraReadOnly())
        original_w = cam.get('width')
        ctrl._widthSpin.setValue(1280)
        ctrl.apply()
        self.assertEqual(cam.get('width'), original_w)

    def test_does_not_call_set_on_readonly_height(self):
        ctrl, src, cam = make_control(FakeCameraReadOnly())
        original_h = cam.get('height')
        ctrl._heightSpin.setValue(720)
        ctrl.apply()
        self.assertEqual(cam.get('height'), original_h)


class TestFinalize(unittest.TestCase):

    def _run_finalize(self, camera=None, resolutions=None):
        ctrl, src, cam = make_control(camera, resolutions)
        ctrl._finalize()
        return ctrl, src, cam

    def test_re_enables_apply_button(self):
        ctrl, _, _ = self._run_finalize()
        self.assertTrue(ctrl._applyBtn.isEnabled())

    def test_re_enables_width_spin(self):
        ctrl, _, _ = self._run_finalize()
        self.assertTrue(ctrl._widthSpin.isEnabled())

    def test_width_spin_reflects_camera_value(self):
        cam = FakeCamera(width=1280, height=720)
        ctrl, _, _ = self._run_finalize(cam)
        self.assertEqual(ctrl._widthSpin.value(), 1280)

    def test_height_spin_reflects_camera_value(self):
        cam = FakeCamera(width=1280, height=720)
        ctrl, _, _ = self._run_finalize(cam)
        self.assertEqual(ctrl._heightSpin.value(), 720)

    def test_fps_spin_reflects_camera_value(self):
        cam = FakeCamera(fps=15.)
        ctrl, _, _ = self._run_finalize(cam)
        self.assertAlmostEqual(ctrl._fpsSpin.value(), 15.)

    def test_result_label_updated(self):
        cam = FakeCamera(fps=24.)
        ctrl, _, _ = self._run_finalize(cam)
        self.assertIn('24.0', ctrl._resultLabel.text())

    def test_dropdown_updated(self):
        cam = FakeCamera(width=1280, height=720)
        ctrl, _, _ = self._run_finalize(cam, resolutions=_RESOLUTIONS)
        self.assertEqual(ctrl._resolutionCombo.currentText(), '1280\u00d7720')

    def test_changed_signal_emitted(self):
        ctrl, _, _ = make_control()
        spy = QtTest.QSignalSpy(ctrl.changed)
        ctrl._finalize()
        self.assertEqual(len(spy), 1)

    def test_changed_carries_width(self):
        cam = FakeCamera(width=1280, height=720, fps=30.)
        ctrl, _, _ = make_control(cam)
        spy = QtTest.QSignalSpy(ctrl.changed)
        ctrl._finalize()
        self.assertEqual(spy[0][0], 1280)

    def test_changed_carries_height(self):
        cam = FakeCamera(width=1280, height=720, fps=30.)
        ctrl, _, _ = make_control(cam)
        spy = QtTest.QSignalSpy(ctrl.changed)
        ctrl._finalize()
        self.assertEqual(spy[0][1], 720)

    def test_changed_carries_fps(self):
        cam = FakeCamera(fps=15.)
        ctrl, _, _ = make_control(cam)
        spy = QtTest.QSignalSpy(ctrl.changed)
        ctrl._finalize()
        self.assertAlmostEqual(spy[0][2], 15.)

    def test_changed_fps_is_none_when_camera_has_no_fps(self):
        ctrl, _, _ = make_control(FakeCameraNoFps())
        spy = QtTest.QSignalSpy(ctrl.changed)
        ctrl._finalize()
        self.assertIsNone(spy[0][2])


class TestOnFirstFrame(unittest.TestCase):

    def test_calls_finalize(self):
        ctrl, src, cam = make_control(FakeCamera(width=1280, height=720))
        src.newFrame.connect(ctrl._onFirstFrame)
        spy = QtTest.QSignalSpy(ctrl.changed)
        ctrl._onFirstFrame(_FRAME.copy())
        self.assertEqual(len(spy), 1)

    def test_disconnects_signal(self):
        ctrl, src, _ = make_control()
        src.newFrame.connect(ctrl._onFirstFrame)
        ctrl._onFirstFrame(_FRAME.copy())
        # After disconnect, emitting newFrame must not call _finalize again
        spy = QtTest.QSignalSpy(ctrl.changed)
        src.newFrame.emit(_FRAME.copy())
        self.assertEqual(len(spy), 0)


if __name__ == '__main__':
    unittest.main()
