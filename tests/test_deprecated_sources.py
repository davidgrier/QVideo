'''Unit tests for the retired Q<Name>Source classes of the backends.'''
import importlib
import unittest
import warnings

from qtpy import QtWidgets

from QVideo.cameras.Noise import QNoiseCamera
from QVideo.cameras._deprecated import deprecated_sources
from QVideo.lib import QCamera, QVideoSource

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class FakeCamera(QCamera):

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.args, self.kwargs = args, kwargs

    def _initialize(self, *args, **kwargs):
        return True

    def _deinitialize(self):
        pass

    def read(self):
        return False, None


def getattr_for(**cameras):
    return deprecated_sources('QVideo.fake', **cameras)


class TestTheShim(unittest.TestCase):

    def source(self, *args, **kwargs):
        make = getattr_for(QFakeSource=FakeCamera)('QFakeSource')
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            result = make(*args, **kwargs)
        self.warnings = caught
        return result

    def test_it_warns_that_the_class_is_deprecated(self):
        self.source()
        self.assertEqual(len(self.warnings), 1)
        self.assertIs(self.warnings[0].category, DeprecationWarning)
        message = str(self.warnings[0].message)
        self.assertIn('QFakeSource is deprecated', message)
        self.assertIn('QVideoSource(FakeCamera(...))', message)

    def test_the_warning_points_at_the_caller(self):
        self.source()
        self.assertEqual(self.warnings[0].filename, __file__)

    def test_it_returns_a_video_source(self):
        self.assertIsInstance(self.source(), QVideoSource)

    def test_it_makes_the_camera_from_the_arguments(self):
        camera = self.source(3, gain=2).source
        self.assertIsInstance(camera, FakeCamera)
        self.assertEqual((camera.args, camera.kwargs), ((3,), {'gain': 2}))

    def test_it_wraps_a_camera_given_by_keyword(self):
        camera = FakeCamera()
        self.assertIs(self.source(camera=camera).source, camera)

    def test_it_wraps_a_camera_given_first(self):
        camera = FakeCamera()
        self.assertIs(self.source(camera).source, camera)

    def test_a_camera_given_first_leaves_the_rest_alone(self):
        camera = FakeCamera()
        self.source(camera, cameraID=2)
        self.assertEqual(camera.kwargs, {})

    def test_any_other_name_is_an_attribute_error(self):
        with self.assertRaises(AttributeError):
            getattr_for(QFakeSource=FakeCamera)('QOtherSource')


class TestThePackages(unittest.TestCase):

    def test_the_noise_package_still_offers_its_source(self):
        from QVideo.cameras.Noise import QNoiseSource
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            source = QNoiseSource(blacklevel=48)
        self.assertIsInstance(source.source, QNoiseCamera)
        self.assertEqual(source.source.blacklevel, 48)
        self.assertEqual(len(caught), 1)

    def test_every_retired_name_is_still_there(self):
        names = {'Noise': 'QNoiseSource', 'OpenCV': 'QOpenCVSource',
                 'Picamera': 'QPicameraSource', 'Basler': 'QBaslerSource',
                 'Flir': 'QFlirSource', 'IDS': 'QIDSSource',
                 'MV': 'QMVSource', 'Vimbax': 'QVimbaXSource',
                 'Viva': 'QVivaSource', 'Genicam': 'QGenicamSource'}
        for package, name in names.items():
            with self.subTest(name=name):
                module = importlib.import_module(f'QVideo.cameras.{package}')
                self.assertTrue(callable(getattr(module, name)))
                self.assertNotIn(name, module.__all__)

    def test_the_imx_source_is_in_the_picamera_package(self):
        module = importlib.import_module('QVideo.cameras.Picamera')
        self.assertTrue(callable(module.QIMXSource))

    def test_a_missing_name_is_still_an_attribute_error(self):
        module = importlib.import_module('QVideo.cameras.Noise')
        with self.assertRaises(AttributeError):
            module.QNoSuchThing


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
