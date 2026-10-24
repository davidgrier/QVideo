'''Unit tests for the lazy QVideo.overlays package.'''
import subprocess
import sys
import unittest


def run(code: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, '-c', code], capture_output=True)


class TestLazyOverlays(unittest.TestCase):

    def test_package_import_loads_no_overlay_module(self):
        result = run('import sys, QVideo.overlays; '
                     'sys.exit(any(m.startswith("QVideo.overlays.") '
                     'for m in sys.modules))')
        self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_trackpy_overlay_does_not_load_yolo(self):
        result = run('import sys, QVideo.overlays.trackpy; '
                     'sys.exit("QVideo.overlays.yolo" in sys.modules)')
        self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_names_resolve_to_their_submodules(self):
        import QVideo.overlays as overlays
        from QVideo.overlays.trackpy import QTrackpyOverlay
        from QVideo.overlays.yolo import QYoloWidget
        self.assertIs(overlays.QTrackpyOverlay, QTrackpyOverlay)
        self.assertIs(overlays.QYoloWidget, QYoloWidget)

    def test_all_names_are_importable(self):
        import QVideo.overlays as overlays
        for name in overlays.__all__:
            self.assertTrue(hasattr(overlays, name), name)

    def test_unknown_name_raises_attribute_error(self):
        import QVideo.overlays as overlays
        with self.assertRaises(AttributeError):
            overlays.NoSuchOverlay


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
