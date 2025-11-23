from QVideo.lib import QListCameras
from harvesters.core import Harvester
from QVideo.cameras.Flir.QFlirCamera import QFlirCamera


class QListFlirCameras(QListCameras):
    '''A QComboBox that lists available Flir cameras.

    Inherits
    --------
    QVideo.lib.QListCameras
    '''

    def _model(self) -> type:
        return QFlirCamera

    def _listCameras(self) -> None:
        h = Harvester()
        h.add_file(QFlirCamera.producer())
        h.update()
        for n, c in enumerate(h.device_info_list):
            p = c.property_dict
            self.addItem(f'{p["model"]} (SN {p["serial_number"]})', n)
        h.reset()


if __name__ == '__main__':
    QListFlirCameras.example()
