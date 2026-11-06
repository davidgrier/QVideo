'''Smoke test of benchmarks/benchmark.py, so that the script does not rot.'''
import importlib.util
import tempfile
import unittest
from pathlib import Path
from qtpy import QtWidgets

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

SCRIPT = Path(__file__).resolve().parent.parent / 'benchmarks' / 'benchmark.py'


def load():
    spec = importlib.util.spec_from_file_location('benchmark', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestBenchmark(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.benchmark = load()

    def test_the_machine_is_described(self):
        info = self.benchmark.machine()
        for key in ('QVideo', 'Python', 'CPU', 'Qt binding', 'OpenCV'):
            self.assertIn(key, info)

    def test_a_synthetic_camera_is_measured(self):
        camera = self.benchmark.PacedCamera((48, 64), 100.)
        self.addCleanup(camera.close)
        result = self.benchmark.measure(camera, seconds=0.6, settle=0.2)
        self.assertEqual(set(result), {'fps', 'p50 ms', 'p99 ms',
                                       'cpu %', 'dropped'})
        self.assertGreater(result['fps'], 50)
        self.assertEqual(result['dropped'], 0)

    def test_tables_are_saved(self):
        rows = [{'a': 1, 'b': 'x,y'}, {'a': 2, 'b': 'z'}]
        with tempfile.TemporaryDirectory() as directory:
            self.benchmark.save(Path(directory), 'table', rows)
            text = (Path(directory) / 'table.csv').read_text()
        self.assertEqual(text.splitlines(), ['a,b', '1,x;y', '2,z'])

    def test_a_table_is_printed(self):
        import contextlib
        import io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.benchmark.show('Title', [{'a': 1, 'b': 22}])
        self.assertIn('Title', out.getvalue())
        self.assertIn('22', out.getvalue())

    def test_the_scene_is_a_gray_frame(self):
        frame = self.benchmark.scene((32, 48))
        self.assertEqual((frame.shape, frame.dtype.name),
                         ((32, 48), 'uint8'))


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
