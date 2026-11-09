'''The demos are imported when they are asked for.'''
import subprocess
import sys
import unittest

import QVideo.demos as demos


def run(code: str, *flags: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *flags, '-c', code],
                          capture_output=True, text=True, timeout=120,
                          env={**__import__('os').environ,
                               'QT_QPA_PLATFORM': 'offscreen'})


class TestLazyDemos(unittest.TestCase):

    def test_every_name_resolves_to_its_class(self):
        for name in demos.__all__:
            with self.subTest(name=name):
                self.assertTrue(isinstance(getattr(demos, name), type))

    def test_the_names_are_listed(self):
        self.assertIn('ROIDemo', dir(demos))
        self.assertIn('ROIDemo', demos.__all__)

    def test_an_unknown_name_is_an_attribute_error(self):
        with self.assertRaises(AttributeError):
            demos.NoSuchDemo       # noqa: B018

    def test_a_demo_is_not_imported_until_it_is_asked_for(self):
        out = run('import sys, QVideo.demos\n'
                  'print("QVideo.demos.roidemo" in sys.modules)\n'
                  'from QVideo.demos import ROIDemo\n'
                  'print("QVideo.demos.roidemo" in sys.modules)')
        self.assertEqual(out.stdout.split(), ['False', 'True'], out.stderr)

    def test_running_a_demo_as_a_module_does_not_warn(self):
        out = run('import runpy, sys\n'
                  'sys.argv = ["x", "-h"]\n'
                  'try:\n'
                  '    runpy.run_module("QVideo.demos.filterrackdemo", '
                  'run_name="__main__")\n'
                  'except SystemExit:\n'
                  '    pass', '-W', 'error::RuntimeWarning')
        self.assertNotIn('RuntimeWarning', out.stderr)
        self.assertIn('usage', out.stdout)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
