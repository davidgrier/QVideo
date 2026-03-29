'''Utilities for probing and configuring camera resolutions via OpenCV.'''
import cv2


__all__ = ['probe_resolutions', 'configure', 'COMMON_RESOLUTIONS']

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
    Restores the original resolution and frame rate when done.

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
    original_fps = device.get(cv2.CAP_PROP_FPS)
    supported: set[tuple[int, int]] = set()
    for w, h in COMMON_RESOLUTIONS:
        device.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        device.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        actual = (int(device.get(cv2.CAP_PROP_FRAME_WIDTH)),
                  int(device.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        supported.add(actual)
    device.set(cv2.CAP_PROP_FRAME_WIDTH, original[0])
    device.set(cv2.CAP_PROP_FRAME_HEIGHT, original[1])
    device.set(cv2.CAP_PROP_FPS, original_fps)
    return sorted(supported)


def configure(device: cv2.VideoCapture,
              width: int | None = None,
              height: int | None = None,
              fps: float | None = 30.) -> None:
    '''Configure an open OpenCV VideoCapture device.

    Three modes:

    - **Explicit** (both *width* and *height* given): apply those values
      directly, then set *fps* if provided.
    - **Quality** (default, *fps* is not ``None``): probe supported
      resolutions and select the largest one, then set *fps*.
    - **Performance** (*fps* is ``None``): probe supported resolutions
      and select the smallest one, letting the driver maximize frame
      rate.

    Parameters
    ----------
    device : cv2.VideoCapture
        An already-open capture device.
    width : int or None
        Desired frame width [pixels].  Must be paired with *height*
        for explicit mode.  ``None`` triggers auto-selection.
    height : int or None
        Desired frame height [pixels].  Must be paired with *width*
        for explicit mode.  ``None`` triggers auto-selection.
    fps : float or None
        Desired frame rate [fps].  ``None`` selects performance mode
        (smallest resolution, driver-maximum frame rate).
        Default: ``30.``.
    '''
    if width is not None and height is not None:
        device.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        device.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        if fps is not None:
            device.set(cv2.CAP_PROP_FPS, fps)
        return

    resolutions = probe_resolutions(device)
    if not resolutions:
        return

    if fps is None:
        # performance mode: smallest resolution, driver-maximum frame rate
        w, h = resolutions[0]
        device.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        device.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        return

    # quality mode: largest resolution that achieves the target frame rate.
    # Iterate from largest to smallest; stop at the first resolution where
    # the driver confirms it can deliver at least 90 % of the target fps.
    for w, h in reversed(resolutions):
        device.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        device.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        device.set(cv2.CAP_PROP_FPS, fps)
        if device.get(cv2.CAP_PROP_FPS) >= fps * 0.9:
            return
    # fallback: all iterations set the smallest resolution last; fps is
    # already requested on the device, clamped to whatever the driver allows.
