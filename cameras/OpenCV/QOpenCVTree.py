from QVideo.lib import QCameraTree
from QVideo.cameras.OpenCV import QOpenCVCamera


class QOpenCVTree(QCameraTree):

    def __init__(self, *args, camera=None, **kwargs):
        camera = camera or QOpenCVCamera()
        '''
        controls = [
            {'name': 'Modifications', 'type': 'group', 'children': [
                {'name': 'Flipped', 'type': 'bool', 'value': False},
                {'name': 'Mirrored', 'type': 'bool', 'value': False},
                {'name': 'Gray', 'type': 'bool', 'value': False}]}
        ]
        '''
        controls = None
        super().__init__(camera, controls, *args, **kwargs)


def example():
    from PyQt5.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)

    widget = QOpenCVTree()
    widget.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    example()
