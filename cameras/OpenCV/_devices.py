'''Camera and format enumeration for OpenCV-backed cameras.'''
import platform
import cv2

try:
    from pyqtgraph.Qt import QtMultimedia as _QtMultimedia
    _QMediaDevices = _QtMultimedia.QMediaDevices
except (ImportError, AttributeError):
    _QMediaDevices = None


__all__ = ['QOpenCVDevices',
           'COMMON_RESOLUTIONS', 'probe_resolutions', 'probe_formats', 'configure']


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


def probe_formats(device: cv2.VideoCapture,
                  resolutions: list[tuple[int, int]] | None = None,
                  ) -> list[tuple[int, int, float, float]]:
    '''Return ``(width, height, 1.0, max_fps)`` for each resolution the device accepts.

    For each candidate resolution, the device is asked to deliver 120 fps
    (above any real hardware limit) and the value the driver accepts is
    recorded as the maximum.  Restores the original resolution and frame rate
    when done.

    Parameters
    ----------
    device : cv2.VideoCapture
        An already-open capture device.
    resolutions : list[tuple[int, int]] or None
        Resolution candidates to probe.  Defaults to
        :data:`COMMON_RESOLUTIONS`.

    Returns
    -------
    list[tuple[int, int, float, float]]
        Sorted list of ``(width, height, 1.0, max_fps)`` tuples, one per
        distinct resolution the device accepts.
    '''
    if resolutions is None:
        resolutions = COMMON_RESOLUTIONS
    original_w = int(device.get(cv2.CAP_PROP_FRAME_WIDTH))
    original_h = int(device.get(cv2.CAP_PROP_FRAME_HEIGHT))
    original_fps = device.get(cv2.CAP_PROP_FPS)
    seen: set[tuple[int, int]] = set()
    results: list[tuple[int, int, float, float]] = []
    for w, h in resolutions:
        device.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        device.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        actual_w = int(device.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(device.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if (actual_w, actual_h) in seen:
            continue
        seen.add((actual_w, actual_h))
        device.set(cv2.CAP_PROP_FPS, 120.)
        max_fps = device.get(cv2.CAP_PROP_FPS)
        if max_fps <= 0:
            max_fps = original_fps if original_fps > 0 else 30.
        results.append((actual_w, actual_h, 1., max_fps))
    device.set(cv2.CAP_PROP_FRAME_WIDTH, original_w)
    device.set(cv2.CAP_PROP_FRAME_HEIGHT, original_h)
    device.set(cv2.CAP_PROP_FPS, original_fps)
    return sorted(results)


def configure(device: cv2.VideoCapture,
              width: int | None = None,
              height: int | None = None,
              fps: float | None = 30.,
              resolutions: list[tuple[int, int]] | None = None) -> None:
    '''Configure an open OpenCV VideoCapture device.

    Three modes:

    - **Explicit** (both *width* and *height* given): apply those values
      directly, then set *fps* if provided.
    - **Quality** (default, *fps* is not ``None``): select the largest
      supported resolution, then set *fps*.
    - **Performance** (*fps* is ``None``): select the smallest supported
      resolution, letting the driver maximize frame rate.

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
    resolutions : list[tuple[int, int]] or None
        Known supported resolutions as ``(width, height)`` pairs.
        When provided, skips trial-and-error probing via
        :func:`probe_resolutions`.  ``None`` (default) triggers probing.
    '''
    if width is not None and height is not None:
        device.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        device.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        if fps is not None:
            device.set(cv2.CAP_PROP_FPS, fps)
        return

    if resolutions is None:
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


class QOpenCVDevices:
    '''Camera discovery and format enumeration for OpenCV cameras.

    Uses :class:`QtMultimedia.QMediaDevices` when available to enumerate
    cameras and their supported formats without opening the device.  Falls
    back to trial-and-error probing via OpenCV when QtMultimedia is not
    present.

    All methods are static — this class is a namespace, not instantiated.
    '''

    @staticmethod
    def cameras() -> list[tuple[int, str]]:
        '''Return a list of available cameras as ``(index, name)`` pairs.

        The index is the integer *cameraID* suitable for passing to
        :class:`~QVideo.cameras.OpenCV.QOpenCVCamera`.

        Returns
        -------
        list[tuple[int, str]]
            ``(cameraID, description)`` for each detected camera, sorted
            by *cameraID*.
        '''
        if _QMediaDevices is not None:
            return [(i, dev.description())
                    for i, dev in enumerate(_QMediaDevices.videoInputs())]
        return QOpenCVDevices._probe_cameras()

    @staticmethod
    def formats(cameraID: int = 0) -> list[tuple[int, int, float, float]]:
        '''Return supported formats for camera *cameraID*.

        Each entry is ``(width, height, 1.0, max_fps)`` where *max_fps* is
        the highest frame rate the driver actually delivers at that resolution,
        determined by opening the device briefly and querying via OpenCV.

        :class:`QtMultimedia.QMediaDevices` is used to obtain the resolution
        list when available (it may know about non-standard resolutions that
        :data:`COMMON_RESOLUTIONS` does not cover).
        Frame rates from QtMultimedia are **not** used because they reflect
        nominal/declared values that often differ from what the driver accepts.

        Parameters
        ----------
        cameraID : int
            Camera index (same convention as OpenCV ``VideoCapture``).

        Returns
        -------
        list[tuple[int, int, float, float]]
            ``(width, height, 1.0, max_fps)`` for each distinct resolution,
            sorted by ``(width, height)``.
        '''
        qt_resolutions = None
        if _QMediaDevices is not None:
            device = QOpenCVDevices._find_device(
                cameraID, _QMediaDevices.videoInputs())
            if device is not None:
                qt_resolutions = [(w, h)
                                  for w, h, *_ in
                                  QOpenCVDevices._formats_from_device(device)]
        return QOpenCVDevices._probe_formats(cameraID, qt_resolutions)

    @staticmethod
    def _find_device(cameraID: int, devices) -> object | None:
        '''Match *cameraID* to a :class:`~QtMultimedia.QCameraDevice`.

        On Linux, ``QCameraDevice.id()`` returns a byte string containing
        the V4L2 device path (e.g. ``b'/dev/video0'``), which maps directly
        to the OpenCV camera index.  On other platforms, the enumeration
        order matches OpenCV, so the index is used directly.

        Parameters
        ----------
        cameraID : int
            OpenCV camera index.
        devices : sequence
            List of :class:`~QtMultimedia.QCameraDevice` objects from
            ``QMediaDevices.videoInputs()``.

        Returns
        -------
        QCameraDevice or None
            The matching device, or ``None`` if not found.
        '''
        if platform.system() == 'Linux':
            # Qt6/GStreamer backend reports IDs as b'v4l2:///dev/videoN';
            # Qt6/V4L2 backend reports b'/dev/videoN'.  Match on the suffix
            # '/videoN' to handle both formats.
            target_suffix = f'/video{cameraID}'.encode()
            for dev in devices:
                dev_id = bytes(dev.id()).rstrip(b'\x00')
                if dev_id.endswith(target_suffix):
                    return dev
            return None
        # macOS: Qt6 and OpenCV both use AVFoundation, enumeration order matches.
        # Windows: Qt6 uses WMF; OpenCV may use DirectShow or MSMF depending on
        # the build.  Index correlation holds when both use the same backend but
        # may fail when virtual cameras (OBS, etc.) cause ordering differences.
        if cameraID < len(devices):
            return devices[cameraID]
        return None

    @staticmethod
    def _formats_from_device(device) -> list[tuple[int, int, float, float]]:
        '''Extract and deduplicate formats from a :class:`~QtMultimedia.QCameraDevice`.

        Multiple :class:`~QtMultimedia.QVideoFormat` entries that share the
        same ``(width, height)`` but differ in pixel format are merged; the
        resulting entry spans the union of their fps ranges.

        Parameters
        ----------
        device : QCameraDevice
            Camera device from ``QMediaDevices.videoInputs()``.

        Returns
        -------
        list[tuple[int, int, float, float]]
            Sorted ``(width, height, min_fps, max_fps)`` for each distinct
            resolution.
        '''
        seen: dict[tuple[int, int], tuple[float, float]] = {}
        for fmt in device.videoFormats():
            w = fmt.resolution().width()
            h = fmt.resolution().height()
            lo = fmt.minFrameRate()
            hi = fmt.maxFrameRate()
            if (w, h) in seen:
                prev_lo, prev_hi = seen[(w, h)]
                seen[(w, h)] = (min(prev_lo, lo), max(prev_hi, hi))
            else:
                seen[(w, h)] = (lo, hi)
        return sorted((w, h, lo, hi) for (w, h), (lo, hi) in seen.items())

    @staticmethod
    def _probe_cameras() -> list[tuple[int, str]]:
        '''Discover cameras by opening each index in turn.

        Tries indices 0–9 and stops at the first one that fails to open.

        Returns
        -------
        list[tuple[int, str]]
            ``(cameraID, name)`` for each detected camera.
        '''
        found = []
        for i in range(10):
            cap = cv2.VideoCapture(i)
            if not cap.isOpened():
                cap.release()
                break
            found.append((i, f'Camera {i}'))
            cap.release()
        return found

    @staticmethod
    def _probe_formats(cameraID: int,
                       resolutions: list[tuple[int, int]] | None = None,
                       ) -> list[tuple[int, int, float, float]]:
        '''Open *cameraID* briefly and return actual ``(w, h, 1.0, max_fps)``
        entries via :func:`probe_formats`.

        Parameters
        ----------
        cameraID : int
            Camera index to probe.
        resolutions : list[tuple[int, int]] or None
            Resolution candidates.  ``None`` uses
            :data:`COMMON_RESOLUTIONS`.

        Returns
        -------
        list[tuple[int, int, float, float]]
            ``(width, height, 1.0, max_fps)`` for each accepted resolution.
        '''
        api = cv2.CAP_V4L2 if platform.system() == 'Linux' else cv2.CAP_ANY
        cap = cv2.VideoCapture(cameraID, api)
        if not cap.isOpened():
            cap.release()
            return []
        result = probe_formats(cap, resolutions)
        cap.release()
        return result
