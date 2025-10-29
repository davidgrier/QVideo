from argparse import ArgumentParser
from QVideo.lib import QCameraTree


def camera_parser(parser: ArgumentParser | None = None) -> ArgumentParser:
    '''Returns a command-line argument parser'''
    parser = parser or ArgumentParser()
    arg = parser.add_argument
    arg('-c', dest='opencv', help='OpenCV camera', action='store_true')
    arg('-f', dest='flir', help='Flir camera', action='store_true')
    arg('-s', dest='spinnaker', help='Spinnaker SDK', action='store_true')
    arg('cameraID', nargs='?', type=int, default=0,
        help='camera ID number (default: %(default)d)')
    return parser


def choose_camera(parser: ArgumentParser | None = None) -> QCameraTree:
    '''Chooses and returns a camera based on command-line arguments.

    Parameters
    ----------
    parser : ArgumentParser | None
        An optional ArgumentParser to parse command-line arguments.
        If provided, camera options will be added to it.
        If None, a new ArgumentParser is created.

    Returns
    -------
    QCameraTree
        The chosen camera object.
    '''
    args, _ = camera_parser(parser).parse_known_args()
    if args.opencv:
        try:
            from QVideo.cameras.OpenCV import QOpenCVTree as Camera
        except ImportError as ex:
            logger.warning(f'Could not import OpenCV camera: {ex}')
    elif args.flir:
        try:
            from QVideo.cameras.Flir import QFlirTree as Camera
        except ImportError as ex:
            logger.warning(f'Could not import Flir camera: {ex}')
    elif args.spinnaker:
        try:
            from QVideo.cameras.Spinnaker import QSpinnakerTree as Camera
        except ImportError as ex:
            logger.warning(f'Could not import Spinnaker SDK camera: {ex}')
    else:
        from QVideo.cameras.Noise import QNoiseTree as Camera

    return Camera(cameraID=args.cameraID)


if __name__ == '__main__':
    args, _ = camera_parser().parse_known_args()
    print(args)
