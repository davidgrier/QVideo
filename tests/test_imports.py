'''Every public module imports in an interpreter of its own.

The other tests run in one process, and many of them put stand-ins for the
packages of the camera vendors in ``sys.modules``.  A backend that imports
an optional package without a guard would pass there and fail on a machine
that does not have the package, which is where most users are.  Here
nothing is mocked: each module is imported by itself, as an application
would import it.

It takes about 15 seconds and fails rarely, so it is skipped unless asked
for::

    QVIDEO_TEST_IMPORTS=1 python -m pytest tests/test_imports.py
'''
import os
import pkgutil
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

#: Packages whose every module is imported, and the packages themselves.
_PACKAGES = ('lib', 'cameras', 'interactive', 'widgets')
_ALL = ('lib', 'cameras', 'interactive', 'widgets', 'filters', 'dvr',
        'overlays', 'demos')

#: Scripts that applications run; they are executed as modules, not as
#: ``__main__``, so that only their imports run.  ``__main__.py`` is left
#: out: it starts the application when it is imported.
_SCRIPTS = ('QCamcorder.py',) + tuple(
    f'demos/{path.name}'
    for path in sorted((ROOT / 'demos').glob('*demo.py')))


def _modules() -> list[str]:
    names = ['QVideo'] + [f'QVideo.{package}' for package in _ALL]
    for package in _PACKAGES:
        names += [f'QVideo.{package}.{module.name}'
                  for module in pkgutil.iter_modules([str(ROOT / package)])]
    # The packages of the backends and the overlays load their optional
    # packages when they are first used, not when 'cameras' is imported.
    for package in ('cameras', 'overlays'):
        names += [f'QVideo.{package}.{module.name}'
                  for module in pkgutil.iter_modules([str(ROOT / package)])
                  if package == 'overlays' or module.ispkg]
    return list(dict.fromkeys(names))


def _import(code: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
    return subprocess.run([sys.executable, '-c', code], env=env,
                          capture_output=True, text=True, timeout=120)


def _problem(result: subprocess.CompletedProcess) -> str:
    return result.stderr.strip().splitlines()[-1] if result.returncode else ''


@unittest.skipUnless(os.environ.get('QVIDEO_TEST_IMPORTS'),
                     'slow; set QVIDEO_TEST_IMPORTS=1 to run')
class TestFirstImport(unittest.TestCase):

    def check(self, targets: list[str], code) -> None:
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda target: _import(code(target)),
                                    targets))
        for target, result in zip(targets, results):
            with self.subTest(target):
                self.assertEqual(result.returncode, 0, _problem(result))

    def test_every_module_imports_first(self):
        self.check(_modules(), lambda name: f'import {name}')

    def test_every_script_imports_first(self):
        self.check(list(_SCRIPTS), lambda path: (
            'import runpy; '
            f"runpy.run_path({str(ROOT / path)!r}, run_name='imported')"))


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
