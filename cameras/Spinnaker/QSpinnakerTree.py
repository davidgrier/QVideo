from QVideo.lib import QCameraTree
from QVideo.cameras.Spinnaker import QSpinnakerCamera


class QSpinnakerTree(QCameraTree):

    def __init__(self, *args, camera=None, **kwargs):
        camera = camera or QSpinnakerCamera()
        controls = [
            {'name': 'Modifications', 'type': 'group', 'children': [
                {'name': 'Flipped', 'type': 'bool', 'value': False},
                {'name': 'Mirrored', 'type': 'bool', 'value': False},
                {'name': 'Gray', 'type': 'bool', 'value': False}]}
        ]
        super().__init__(camera, controls, *args, **kwargs)


if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)

    widget = QSpinnakerTree()
    widget.show()

    sys.exit(app.exec())
