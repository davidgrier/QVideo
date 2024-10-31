from QVideo.lib import QCameraTree
from QVideo.cameras.OpenCV import QOpenCVCamera
from typing import Optional


class QOpenCVTree(QCameraTree):

    def __init__(self, *args,
                 camera: Optional[QOpenCVCamera] = None,
                 **kwargs) -> None:
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


def example() -> None:
    from PyQt5.QtWidgets import QApplication
    import sys
    from pprint import pprint

    app = QApplication(sys.argv)
    widget = QOpenCVTree().start()
    widget.show()
    print(widget.camera.name)
    pprint(widget.camera.settings())
    sys.exit(app.exec())


if __name__ == '__main__':
    example()
