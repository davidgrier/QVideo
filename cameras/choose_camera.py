from argparse import ArgumentParser
import logging


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


__all__ = 'choose_camera choose_camera_widget'.split()


def camera_parser(parser: ArgumentParser | None = None) -> ArgumentParser:
    parser = parser or ArgumentParser()
    arg = parser.add_argument
    arg('-c', dest='opencv', help='OpenCV camera', action='store_true')
    arg('-f', dest='flir', help='Flir camera', action='store_true')
    arg('-s', dest='spinnaker', help='Spinnaker SDK', action='store_true')
    return parser


def choose_camera(parser: ArgumentParser | None = None) -> ArgumentParser:
    args, _ = camera_parser(parser).parse_known_args()
    if args.opencv:
        try:
            from QVideo.cameras.OpenCV import QOpenCVCamera
            return QOpenCVCamera
        except ImportError as ex:
            logger.warning(f'Could not import OpenCV camera: {ex}')

    if args.flir:
        try:
            from QVideo.cameras.Flir import QFlirCamera
            return QFlirCamera
        except ImportError as ex:
            logger.warning(f'Could not import Flir camera: {ex}')

    if args.spinnaker:
        try:
            from QVideo.cameras.Spinnaker import QSpinnakerCamera
            return QSpinnakerCamera
        except ImportError as ex:
            logger.warning(f'Could not import Spinnaker camera: {ex}')

    from QVideo.cameras.Noise import QNoiseSource
    return QNoiseSource


def choose_camera_widget(parser: ArgumentParser | None = None) -> ArgumentParser:
    args, _ = camera_parser(parser).parse_known_args()
    if args.opencv:
        try:
            from QVideo.cameras.OpenCV import QOpenCVTree
            return QOpenCVTree
        except ImportError as ex:
            logger.warning(f'Could not import OpenCV widget: {ex}')

    if args.flir:
        try:
            from QVideo.cameras.Flir import QFlirTree
            return QFlirTree
        except ImportError as ex:
            logger.warning(f'COuld not import Flir widget: {ex}')

    if args.spinnaker:
        try:
            from QVideo.cameras.Spinnaker import QSpinnakerTree
            return QSpinnakerTree
        except ImportError as ex:
            logger.warning(f'Could not import Spinnaker widget: {ex}')

    from QVideo.cameras.Noise import QNoiseTree
    return QNoiseTree
