'''Unit tests for lib/resolutions.py'''
import unittest
import cv2
from unittest.mock import MagicMock, patch
import QVideo.lib.resolutions as resolutions_module
from QVideo.lib.resolutions import probe_resolutions, configure, COMMON_RESOLUTIONS


def make_fps_clamped_device(fps_limits: dict,
                             resolutions: list[tuple[int, int]] | None = None):
    '''Return a mock device that clamps fps per resolution.

    Parameters
    ----------
    fps_limits : dict[(int, int), float]
        Maps (width, height) to the maximum fps the device delivers at
        that resolution.  Resolutions absent from the dict are treated
        as supporting any fps (default 30 fps cap).
    resolutions : list[(int, int)] or None
        Resolutions the device accepts; defaults to the keys of
        *fps_limits* if not given.
    '''
    device = MagicMock(spec=cv2.VideoCapture)
    state = {'w': 640, 'h': 480, 'fps': 30.0}

    def _get(prop):
        if prop == cv2.CAP_PROP_FRAME_WIDTH:
            return float(state['w'])
        if prop == cv2.CAP_PROP_FRAME_HEIGHT:
            return float(state['h'])
        if prop == cv2.CAP_PROP_FPS:
            return state['fps']
        return 0.0

    def _set(prop, value):
        if prop == cv2.CAP_PROP_FRAME_WIDTH:
            state['w'] = int(value)
            state['fps'] = 5.0      # driver lowers fps on format change
        elif prop == cv2.CAP_PROP_FRAME_HEIGHT:
            state['h'] = int(value)
            state['fps'] = 5.0
        elif prop == cv2.CAP_PROP_FPS:
            limit = fps_limits.get((state['w'], state['h']), 30.0)
            state['fps'] = min(float(value), limit)

    device.get.side_effect = _get
    device.set.side_effect = _set
    return device, state


def make_device(accepted: tuple[int, int] | None = None,
                original: tuple[int, int] = (640, 480),
                fps: float = 30.0):
    '''Return a mock cv2.VideoCapture.

    Parameters
    ----------
    accepted : tuple[int, int] or None
        Fixed resolution the device clamps all requests to.
        If None, the device accepts whatever is set.
    original : tuple[int, int]
        Width and height returned before any set() calls.
    fps : float
        Initial frame rate returned before any set() calls.
    '''
    device = MagicMock(spec=cv2.VideoCapture)
    state = {'w': original[0], 'h': original[1], 'fps': fps}

    def _get(prop):
        if prop == cv2.CAP_PROP_FRAME_WIDTH:
            return float(state['w'])
        if prop == cv2.CAP_PROP_FRAME_HEIGHT:
            return float(state['h'])
        if prop == cv2.CAP_PROP_FPS:
            return state['fps']
        return 0.0

    def _set(prop, value):
        if prop == cv2.CAP_PROP_FPS:
            state['fps'] = float(value)
            return
        if accepted is not None:
            state['w'], state['h'] = accepted
            state['fps'] = 5.0   # simulate driver lowering fps on format change
        else:
            if prop == cv2.CAP_PROP_FRAME_WIDTH:
                state['w'] = int(value)
            elif prop == cv2.CAP_PROP_FRAME_HEIGHT:
                state['h'] = int(value)

    device.get.side_effect = _get
    device.set.side_effect = _set
    return device, state


class TestProbeResolutions(unittest.TestCase):

    def test_returns_list(self):
        device, _ = make_device()
        result = probe_resolutions(device)
        self.assertIsInstance(result, list)

    def test_each_element_is_two_tuple(self):
        device, _ = make_device()
        for item in probe_resolutions(device):
            self.assertIsInstance(item, tuple)
            self.assertEqual(len(item), 2)

    def test_result_is_sorted(self):
        device, _ = make_device()
        result = probe_resolutions(device)
        self.assertEqual(result, sorted(result))

    def test_no_duplicates(self):
        device, _ = make_device()
        result = probe_resolutions(device)
        self.assertEqual(len(result), len(set(result)))

    def test_device_accepting_all_resolutions(self):
        '''A compliant device returns one entry per COMMON_RESOLUTIONS entry.'''
        device, _ = make_device()
        result = probe_resolutions(device)
        self.assertEqual(len(result), len(COMMON_RESOLUTIONS))

    def test_device_clamping_to_one_resolution(self):
        '''A device that always clamps returns exactly one entry.'''
        device, _ = make_device(accepted=(640, 480))
        result = probe_resolutions(device)
        self.assertEqual(result, [(640, 480)])

    def test_original_resolution_restored(self):
        '''probe_resolutions must leave the device at its original resolution.'''
        original = (1280, 720)
        device, state = make_device(original=original)
        probe_resolutions(device)
        self.assertEqual((state['w'], state['h']), original)

    def test_original_fps_restored(self):
        '''probe_resolutions must leave the device at its original frame rate.'''
        device, state = make_device(accepted=(640, 480), fps=30.0)
        probe_resolutions(device)
        self.assertAlmostEqual(state['fps'], 30.0)

    def test_elements_are_integers(self):
        device, _ = make_device()
        for w, h in probe_resolutions(device):
            self.assertIsInstance(w, int)
            self.assertIsInstance(h, int)

    def test_set_called_for_each_candidate(self):
        '''Width and height must be set once per candidate resolution.'''
        device, _ = make_device()
        probe_resolutions(device)
        # Two set() calls per candidate (width + height), plus three restore calls
        # (width, height, fps)
        expected_calls = len(COMMON_RESOLUTIONS) * 2 + 3
        self.assertEqual(device.set.call_count, expected_calls)


class TestConfigure(unittest.TestCase):

    _RESOLUTIONS = [(640, 480), (1280, 720), (1920, 1080)]

    def _patch_probe(self, resolutions=None):
        '''Context manager patching probe_resolutions to return *resolutions*.'''
        if resolutions is None:
            resolutions = self._RESOLUTIONS
        return patch.object(resolutions_module, 'probe_resolutions',
                            return_value=resolutions)

    def test_quality_mode_picks_largest_resolution_at_target_fps(self):
        '''Quality mode iterates from largest to smallest and stops at the
        first resolution where the driver confirms ≥ 90 % of target fps.'''
        fps_limits = {(1920, 1080): 10.0}   # 1920×1080 capped; others OK at 30
        device, state = make_fps_clamped_device(fps_limits)
        with self._patch_probe():
            configure(device, fps=30.)
        self.assertEqual(state['w'], 1280)
        self.assertEqual(state['h'], 720)

    def test_quality_mode_uses_largest_when_all_support_fps(self):
        fps_limits = {}  # all resolutions support 30 fps
        device, state = make_fps_clamped_device(fps_limits)
        with self._patch_probe():
            configure(device, fps=30.)
        self.assertEqual(state['w'], 1920)
        self.assertEqual(state['h'], 1080)

    def test_quality_mode_fallback_to_smallest_when_no_resolution_meets_fps(self):
        '''When no resolution achieves target fps, the smallest is used.'''
        fps_limits = {(640, 480): 5.0, (1280, 720): 5.0, (1920, 1080): 5.0}
        device, state = make_fps_clamped_device(fps_limits)
        with self._patch_probe():
            configure(device, fps=30.)
        self.assertEqual(state['w'], 640)
        self.assertEqual(state['h'], 480)

    def test_performance_mode_picks_smallest_resolution(self):
        device, state = make_fps_clamped_device({})
        with self._patch_probe():
            configure(device, fps=None)
        self.assertEqual(state['w'], 640)
        self.assertEqual(state['h'], 480)

    def test_performance_mode_does_not_set_fps(self):
        device, state = make_fps_clamped_device({})
        with self._patch_probe():
            configure(device, fps=None)
        fps_calls = [c for c in device.set.call_args_list
                     if c.args[0] == cv2.CAP_PROP_FPS]
        self.assertEqual(len(fps_calls), 0)

    def test_explicit_mode_sets_width_height_fps(self):
        device, state = make_fps_clamped_device({})
        configure(device, width=800, height=600, fps=15.)
        self.assertEqual(state['w'], 800)
        self.assertEqual(state['h'], 600)
        self.assertAlmostEqual(state['fps'], 15.)

    def test_explicit_mode_skips_probing(self):
        device, state = make_fps_clamped_device({})
        with patch.object(resolutions_module, 'probe_resolutions') as mock_probe:
            configure(device, width=800, height=600, fps=15.)
        mock_probe.assert_not_called()

    def test_explicit_mode_without_fps_does_not_set_fps(self):
        device, state = make_fps_clamped_device({})
        configure(device, width=800, height=600, fps=None)
        fps_calls = [c for c in device.set.call_args_list
                     if c.args[0] == cv2.CAP_PROP_FPS]
        self.assertEqual(len(fps_calls), 0)

    def test_empty_resolutions_returns_without_error(self):
        device, state = make_fps_clamped_device({})
        with self._patch_probe(resolutions=[]):
            configure(device, fps=30.)
        # device state unchanged — no set() call for width/height


if __name__ == '__main__':
    unittest.main()
