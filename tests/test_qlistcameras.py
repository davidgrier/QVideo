'''Unit tests for QListCameras.'''
import unittest
from unittest.mock import MagicMock
from pyqtgraph.Qt import QtWidgets
from QVideo.lib.QListCameras import QListCameras


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class ConcreteListCameras(QListCameras):
    '''Concrete subclass for testing override hooks.'''

    class FakeCamera:
        pass

    def _model(self) -> type:
        return self.FakeCamera

    def _listCameras(self) -> None:
        self.addItem('Camera A', 0)
        self.addItem('Camera B', 1)


class TestQListCamerasNotImplemented(unittest.TestCase):

    def test_instantiation_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            QListCameras()

    def test_list_cameras_raises_not_implemented(self):
        combo = ConcreteListCameras.__new__(ConcreteListCameras)
        with self.assertRaises(NotImplementedError):
            QListCameras._listCameras(combo)

    def test_model_raises_not_implemented(self):
        combo = ConcreteListCameras.__new__(ConcreteListCameras)
        with self.assertRaises(NotImplementedError):
            QListCameras._model(combo)


class TestQListCamerasInit(unittest.TestCase):

    def test_creates_successfully(self):
        combo = ConcreteListCameras()
        self.assertIsInstance(combo, QListCameras)

    def test_placeholder_item_present_after_init(self):
        combo = ConcreteListCameras()
        self.assertEqual(combo.itemText(0), 'Select Camera')

    def test_placeholder_data_is_minus_one(self):
        combo = ConcreteListCameras()
        self.assertEqual(combo.itemData(0), -1)


class TestQListCamerasRefresh(unittest.TestCase):

    def test_refresh_clears_existing_items(self):
        combo = ConcreteListCameras()
        combo.addItem('Stale Entry', 99)
        combo.refresh()
        # placeholder + Camera A + Camera B
        self.assertEqual(combo.count(), 3)

    def test_refresh_restores_placeholder(self):
        combo = ConcreteListCameras()
        combo.refresh()
        self.assertEqual(combo.itemText(0), 'Select Camera')
        self.assertEqual(combo.itemData(0), -1)


class TestQListCamerasCameraSelection(unittest.TestCase):

    def test_camera_selected_signal_emitted_on_index_change(self):
        combo = ConcreteListCameras()
        handler = MagicMock()
        combo.cameraSelected.connect(handler)
        combo.setCurrentIndex(1)  # Camera A
        handler.assert_called()

    def test_camera_selected_not_emitted_for_placeholder(self):
        combo = ConcreteListCameras()
        handler = MagicMock()
        combo.cameraSelected.connect(handler)
        combo.setCurrentIndex(1)
        handler.reset_mock()
        combo.setCurrentIndex(0)  # back to placeholder
        handler.assert_not_called()

    def test_camera_selected_not_emitted_on_refresh(self):
        combo = ConcreteListCameras()
        handler = MagicMock()
        combo.cameraSelected.connect(handler)
        combo.refresh()
        handler.assert_not_called()

    def test_camera_selected_emits_model_class(self):
        combo = ConcreteListCameras()
        received = []
        combo.cameraSelected.connect(lambda m, i: received.append((m, i)))
        combo.setCurrentIndex(1)
        self.assertIs(received[-1][0], ConcreteListCameras.FakeCamera)

    def test_camera_selected_emits_device_index(self):
        combo = ConcreteListCameras()
        received = []
        combo.cameraSelected.connect(lambda m, i: received.append((m, i)))
        combo.setCurrentIndex(1)
        self.assertEqual(received[-1][1], 0)  # Camera A has device index 0

    def test_camera_selected_emits_correct_index_for_second_camera(self):
        combo = ConcreteListCameras()
        received = []
        combo.cameraSelected.connect(lambda m, i: received.append((m, i)))
        combo.setCurrentIndex(2)
        self.assertEqual(received[-1][1], 1)  # Camera B has device index 1


class TestConcreteSubclass(unittest.TestCase):

    def test_subclass_populates_cameras(self):
        combo = ConcreteListCameras()
        # placeholder + Camera A + Camera B
        self.assertEqual(combo.count(), 3)

    def test_subclass_model_returns_camera_class(self):
        combo = ConcreteListCameras()
        self.assertIs(combo._model(), ConcreteListCameras.FakeCamera)

    def test_subclass_camera_labels(self):
        combo = ConcreteListCameras()
        self.assertEqual(combo.itemText(1), 'Camera A')
        self.assertEqual(combo.itemText(2), 'Camera B')


if __name__ == '__main__':
    unittest.main()
