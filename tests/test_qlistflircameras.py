'''Unit tests for cameras.Flir.QListFlirCameras.'''
import sys
import unittest
from unittest.mock import MagicMock, patch
from qtpy import QtWidgets

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

# ---------------------------------------------------------------------------
# Genicam / harvesters stubs must be present before the module is imported.
# ---------------------------------------------------------------------------

_mock_harvesters_core = MagicMock()
_mock_harvesters      = MagicMock()
_mock_harvesters.core = _mock_harvesters_core

for _name, _mod in [('harvesters',      _mock_harvesters),
                    ('harvesters.core', _mock_harvesters_core),
                    ('genicam',         MagicMock()),
                    ('genicam.genapi',  MagicMock()),
                    ('genicam.gentl',   MagicMock())]:
    sys.modules.setdefault(_name, _mod)

from QVideo.cameras.Flir.QListFlirCameras import QListFlirCameras  # noqa: E402
from QVideo.cameras.Flir._camera          import QFlirCamera       # noqa: E402
from QVideo.lib                            import QListCameras      # noqa: E402

_MODULE = sys.modules['QVideo.cameras.Flir.QListFlirCameras']


def make_widget():
    '''Instantiate QListFlirCameras with mocked hardware.'''
    with patch.object(QFlirCamera, 'producer', MagicMock()):
        return QListFlirCameras()


class TestQListFlirCamerasSubclass(unittest.TestCase):

    def test_is_subclass_of_qlistcameras(self):
        widget = make_widget()
        self.assertIsInstance(widget, QListCameras)


class TestQListFlirCamerasModel(unittest.TestCase):

    def test_model_returns_qflircamera(self):
        widget = make_widget()
        self.assertIs(widget._model(), QFlirCamera)


class TestQListFlirCamerasInit(unittest.TestCase):

    def test_creates_successfully(self):
        widget = make_widget()
        self.assertIsInstance(widget, QListFlirCameras)

    def test_placeholder_item_present(self):
        widget = make_widget()
        self.assertEqual(widget.itemText(0), 'Select Camera')

    def test_harvester_add_file_called(self):
        mock_h = MagicMock()
        mock_h.device_info_list = []
        with patch.object(QFlirCamera, 'producer', MagicMock()), \
             patch.object(_MODULE, 'Harvester', return_value=mock_h):
            QListFlirCameras()
        mock_h.add_file.assert_called_once()

    def test_harvester_reset_called(self):
        mock_h = MagicMock()
        mock_h.device_info_list = []
        with patch.object(QFlirCamera, 'producer', MagicMock()), \
             patch.object(_MODULE, 'Harvester', return_value=mock_h):
            QListFlirCameras()
        mock_h.reset.assert_called_once()

    def test_camera_items_added_for_each_device(self):
        cam_info = MagicMock()
        cam_info.property_dict = {'model': 'BlackflyS', 'serial_number': '98765'}
        mock_h = MagicMock()
        mock_h.device_info_list = [cam_info]
        with patch.object(QFlirCamera, 'producer', MagicMock()), \
             patch.object(_MODULE, 'Harvester', return_value=mock_h):
            widget = QListFlirCameras()
        self.assertEqual(widget.count(), 2)   # placeholder + 1 camera
        self.assertIn('BlackflyS', widget.itemText(1))
        self.assertIn('98765', widget.itemText(1))

    def test_camera_item_data_is_device_index(self):
        cam_info = MagicMock()
        cam_info.property_dict = {'model': 'Oryx', 'serial_number': '11111'}
        mock_h = MagicMock()
        mock_h.device_info_list = [cam_info]
        with patch.object(QFlirCamera, 'producer', MagicMock()), \
             patch.object(_MODULE, 'Harvester', return_value=mock_h):
            widget = QListFlirCameras()
        self.assertEqual(widget.itemData(1), 0)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
