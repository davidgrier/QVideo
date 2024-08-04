import argparse
import logging


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


__all__ = ['choose_camera', 'choose_camera_widget']


def parse_command_line():
    parser = argparse.ArgumentParser()
    opt = dict(action='store_true')
    arg = parser.add_argument
    arg('-c', dest='opencv', help='OpenCV camera', **opt)
    arg('-s', dest='spinnaker', help='Spinnaker camera', **opt)
    return parser.parse_known_args()


def choose_camera():
    args, _ = parse_command_line()
    if args.opencv:
        try:
            from QVideo.cameras.OpenCV import QOpenCVCamera
            return QOpenCVCamera
        except ImportError as ex:
            logger.warning(f'Could not import OpenCV camera: {ex}')
    if args.spinnaker:
        try:
            from QVideo.cameras.Spinnaker import QSpinnakerCamera
            return QSpinnakerCamera
        except ImportError as ex:
            logger.warning(f'Could not import Spinnaker camera: {ex}')
    from QVideo.cameras.Noise import QNoiseCamera
    return QNoiseCamera


def choose_camera_widget():
    args, _ = parse_command_line()
    if args.opencv:
        try:
            from QVideo.cameras.OpenCV import QOpenCVTree as QOpenCVWidget
            return QOpenCVWidget
        except ImportError as ex:
            logger.warning(f'Could not import OpenCV camera: {ex}')
    if args.spinnaker:
        try:
            from QVideo.cameras.Spinnaker import QSpinnakerWidget
            return QSpinnakerWidget
        except ImportError as ex:
            logger.warning(f'Could not import Spinnaker camera: {ex}')
    from QVideo.cameras.Noise import QNoiseTree as QNoiseWidget
    return QNoiseWidget
