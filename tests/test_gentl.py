'''Unit tests for cameras/gentl.py and lib/errors.py.'''
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from QVideo.cameras import gentl
from QVideo.lib.errors import QCameraError, QDeviceError, QDriverError


class TestErrors(unittest.TestCase):

    def test_hierarchy(self):
        self.assertTrue(issubclass(QDriverError, QCameraError))
        self.assertTrue(issubclass(QDeviceError, QCameraError))
        self.assertTrue(issubclass(QCameraError, RuntimeError))


class TestGentlPaths(unittest.TestCase):

    def test_unset(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(gentl.gentlPaths(), [])

    def test_empty_entries_dropped(self):
        value = os.pathsep.join(['', '/a', '', '/b'])
        with patch.dict(os.environ, {gentl.ENV: value}):
            self.assertEqual(gentl.gentlPaths(), ['/a', '/b'])

    def test_empty_value_does_not_search_cwd(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'x.cti').touch()
            cwd = os.getcwd()
            os.chdir(d)
            try:
                with patch.dict(os.environ, {gentl.ENV: ''}):
                    self.assertIsNone(gentl.findProducer('x.cti'))
            finally:
                os.chdir(cwd)


class TestFindProducer(unittest.TestCase):

    def test_finds_first_filename_on_path(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'b.cti').touch()
            (Path(d) / 'a.cti').touch()
            with patch.dict(os.environ, {gentl.ENV: d}):
                self.assertEqual(gentl.findProducer('a.cti', 'b.cti'),
                                 str(Path(d) / 'a.cti'))

    def test_returns_none_when_missing(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.dict(os.environ, {gentl.ENV: d}):
                self.assertIsNone(gentl.findProducer('a.cti'))


class TestCheck(unittest.TestCase):

    def _failures(self, results):
        return [m for ok, m in results if not ok]

    def test_reports_missing_packages(self):
        with patch.dict(sys.modules, {'genicam.genapi': None,
                                      'harvesters.core': None}), \
             patch.dict(os.environ, {}, clear=True):
            results = gentl.check('a.cti')
        failures = ' '.join(self._failures(results))
        self.assertIn('cannot import genicam.genapi', failures)
        self.assertIn('pip install genicam harvesters', failures)

    def test_reports_unset_env_and_missing_file(self):
        with patch.dict(os.environ, {}, clear=True):
            results = gentl.check('a.cti')
        failures = ' '.join(self._failures(results))
        self.assertIn('GENICAM_GENTL64_PATH is not set', failures)
        self.assertIn('a.cti not found', failures)

    def test_reports_cameras_when_all_ok(self):
        info = MagicMock()
        info.property_dict = {'model': 'Blackfly', 'serial_number': '42'}
        harvester = MagicMock()
        harvester.device_info_list = [info]
        harvester_core = MagicMock()
        harvester_core.Harvester.return_value = harvester
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'a.cti').touch()
            modules = {'genicam.genapi': MagicMock(),
                       'harvesters.core': harvester_core}
            with patch.dict(sys.modules, modules), \
                 patch.dict(os.environ, {gentl.ENV: d}):
                results = gentl.check('a.cti')
        self.assertEqual(self._failures(results), [])
        self.assertTrue(any('Blackfly' in m for _, m in results))
        harvester.reset.assert_called_once()

    def test_reports_producer_load_failure(self):
        harvester = MagicMock()
        harvester.add_file.side_effect = OSError('bad elf')
        harvester_core = MagicMock()
        harvester_core.Harvester.return_value = harvester
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'a.cti').touch()
            modules = {'genicam.genapi': MagicMock(),
                       'harvesters.core': harvester_core}
            with patch.dict(sys.modules, modules), \
                 patch.dict(os.environ, {gentl.ENV: d}):
                results = gentl.check('a.cti')
        self.assertIn('bad elf', ' '.join(self._failures(results)))
        harvester.reset.assert_called_once()

    def test_without_filenames_lists_all_producers(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'one.cti').touch()
            with patch.dict(os.environ, {gentl.ENV: d}):
                results = gentl.check()
        self.assertTrue(any('1 GenTL producer' in m for _, m in results))


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
