'''Unit tests for lib/resolutions.py'''
import unittest
import cv2
from unittest.mock import MagicMock
from QVideo.lib.resolutions import probe_resolutions, COMMON_RESOLUTIONS


def make_device(accepted: tuple[int, int] | None = None,
                original: tuple[int, int] = (640, 480)):
    '''Return a mock cv2.VideoCapture.

    Parameters
    ----------
    accepted : tuple[int, int] or None
        Fixed resolution the device clamps all requests to.
        If None, the device accepts whatever is set.
    original : tuple[int, int]
        Width and height returned before any set() calls.
    '''
    device = MagicMock(spec=cv2.VideoCapture)
    state = {'w': original[0], 'h': original[1]}

    def _get(prop):
        if prop == cv2.CAP_PROP_FRAME_WIDTH:
            return float(state['w'])
        if prop == cv2.CAP_PROP_FRAME_HEIGHT:
            return float(state['h'])
        return 0.0

    def _set(prop, value):
        if accepted is not None:
            state['w'], state['h'] = accepted
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

    def test_elements_are_integers(self):
        device, _ = make_device()
        for w, h in probe_resolutions(device):
            self.assertIsInstance(w, int)
            self.assertIsInstance(h, int)

    def test_set_called_for_each_candidate(self):
        '''Width and height must be set once per candidate resolution.'''
        device, _ = make_device()
        probe_resolutions(device)
        # Two set() calls per candidate (width + height), plus two restore calls
        expected_calls = len(COMMON_RESOLUTIONS) * 2 + 2
        self.assertEqual(device.set.call_count, expected_calls)


if __name__ == '__main__':
    unittest.main()
