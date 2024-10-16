from QVideo.lib import QCameraTree
from QVideo.cameras.Spinnaker import QSpinnakerCamera
from typing import Optional


class QSpinnakerTree(QCameraTree):

    def __init__(self, *args,
                 camera: Optional[QSpinnakerCamera] = None,
                 **kwargs) -> None:
        camera = camera or QSpinnakerCamera()
        controls = None # self.get_controls(camera)
        super().__init__(camera, controls, *args, **kwargs)

    @staticmethod
    def get_controls(camera):
        def get_control(camera, key):
            value = getattr(camera, key)
            vtype = value.__class__.__name__
            return {'name': key, 'type': vtype, 'value': value}

        geometry = {'name': 'Geometry',
                    'type': 'group',
                    'children': [
                        get_control(camera, 'width'),
                        get_control(camera, 'height')]}
        return [geometry]



def example() -> None:
    from PyQt5.QtWidgets import QApplication
    import sys
    import logging

    module = 'QVideo.cameras.Spinnaker.QSpinnakerCamera'
    logging.getLogger(module).setLevel(logging.ERROR)

    app = QApplication(sys.argv)
    widget = QSpinnakerTree().start()
    widget.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    example()
