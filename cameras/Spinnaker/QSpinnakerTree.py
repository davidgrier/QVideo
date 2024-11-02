from QVideo.lib import (QCameraTree, QVideoSource)
from QVideo.cameras.Spinnaker import QSpinnakerCamera
from typing import Optional


class QSpinnakerTree(QCameraTree):

    def __init__(self, *args,
                 camera: Optional[QCameraTree.Souce] = None,
                 **kwargs) -> None:
        camera = camera or QSpinnakerCamera(*args, **kwargs)
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


if __name__ == '__main__':
    QSpinnakerTree.example()
