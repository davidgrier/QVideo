'''Utilities for probing supported camera resolutions via OpenCV.'''
import cv2


__all__ = ['probe_resolutions', 'COMMON_RESOLUTIONS']

COMMON_RESOLUTIONS: list[tuple[int, int]] = [
    (160, 120),
    (320, 240),
    (640, 480),
    (800, 600),
    (1280, 720),
    (1920, 1080),
    (2560, 1440),
    (3840, 2160),
]


def probe_resolutions(device: cv2.VideoCapture) -> list[tuple[int, int]]:
    '''Return resolutions accepted by an open OpenCV VideoCapture device.

    Probes each entry in :data:`COMMON_RESOLUTIONS` by writing width and
    height to the device and reading back what it actually accepted.
    Restores the original resolution when done.

    Parameters
    ----------
    device : cv2.VideoCapture
        An already-open capture device.

    Returns
    -------
    list[tuple[int, int]]
        Sorted list of ``(width, height)`` pairs accepted by the device.
    '''
    original = (int(device.get(cv2.CAP_PROP_FRAME_WIDTH)),
                int(device.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    supported: set[tuple[int, int]] = set()
    for w, h in COMMON_RESOLUTIONS:
        device.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        device.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        actual = (int(device.get(cv2.CAP_PROP_FRAME_WIDTH)),
                  int(device.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        supported.add(actual)
    device.set(cv2.CAP_PROP_FRAME_WIDTH, original[0])
    device.set(cv2.CAP_PROP_FRAME_HEIGHT, original[1])
    return sorted(supported)
