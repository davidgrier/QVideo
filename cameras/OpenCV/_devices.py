'''Camera and format enumeration for OpenCV-backed cameras.'''
import platform
import re
from typing import NamedTuple

import cv2

try:
    from qtpy import QtMultimedia as _QtMultimedia
    _QMediaDevices = _QtMultimedia.QMediaDevices
except (ImportError, AttributeError):
    _QMediaDevices = None


__all__ = ['QOpenCVDevices', 'CameraDevice', 'COMMON_RESOLUTIONS',
           'capture_backend', 'probe_resolutions', 'probe_formats',
           'configure']


class CameraDevice(NamedTuple):
    '''A camera as the system lists it.

    Attributes
    ----------
    index : int
        The *cameraID* that OpenCV opens the camera by.  It is not the
        position of the camera in the list of Qt, and it can change when a
        camera is plugged in or removed.
    name : str
        The name that the system gives the camera.
    id : str
        The identifier that the system gives the device, empty when it
        gives none.  It is what stays with the camera: on macOS the
        ``uniqueID`` of AVFoundation (a UUID for a built-in camera, and for a
        USB camera the location and the ids of the vendor and product, so
        two cameras of one model differ by their ports); on Linux the path
        ``/dev/videoN``.
    '''

    index: int
    name: str
    id: str


def capture_backend() -> int:
    '''Return the preferred ``cv2.VideoCapture`` backend for this platform.

    Returns
    -------
    int
        ``cv2.CAP_V4L2`` on Linux, ``cv2.CAP_MSMF`` on Windows,
        ``cv2.CAP_AVFOUNDATION`` on macOS, and ``cv2.CAP_ANY`` elsewhere.
    '''
    match platform.system():
        case 'Linux':
            return cv2.CAP_V4L2
        case 'Windows':
            return cv2.CAP_MSMF
        case 'Darwin':
            return cv2.CAP_AVFOUNDATION
        case _:
            return cv2.CAP_ANY


def _size(device: cv2.VideoCapture) -> tuple[int, int]:
    '''Return the width and the height that *device* reports.'''
    return (int(device.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(device.get(cv2.CAP_PROP_FRAME_HEIGHT)))


def _resize(device: cv2.VideoCapture, width: int, height: int) -> None:
    '''Ask *device* for a width and a height.'''
    device.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    device.set(cv2.CAP_PROP_FRAME_HEIGHT, height)


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
    original = _size(device)
    original_fps = device.get(cv2.CAP_PROP_FPS)
    supported: set[tuple[int, int]] = set()
    for w, h in COMMON_RESOLUTIONS:
        _resize(device, w, h)
        supported.add(_size(device))
    _resize(device, *original)
    device.set(cv2.CAP_PROP_FPS, original_fps)
    return sorted(supported)


def probe_formats(device: cv2.VideoCapture,
                  resolutions: list[tuple[int, int]] | None = None,
                  ) -> list[tuple[int, int, float, float]]:
    '''Return ``(width, height, 1.0, max_fps)`` for each accepted resolution.

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
    original = _size(device)
    original_fps = device.get(cv2.CAP_PROP_FPS)
    formats: dict[tuple[int, int], tuple[int, int, float, float]] = {}
    for w, h in resolutions:
        _resize(device, w, h)
        actual = _size(device)
        if actual in formats:
            continue
        device.set(cv2.CAP_PROP_FPS, 120.)
        max_fps = device.get(cv2.CAP_PROP_FPS)
        if max_fps <= 0:
            max_fps = original_fps if original_fps > 0 else 30.
        formats[actual] = (*actual, 1., max_fps)
    _resize(device, *original)
    device.set(cv2.CAP_PROP_FPS, original_fps)
    return sorted(formats.values())


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
        _resize(device, width, height)
        if fps is not None:
            device.set(cv2.CAP_PROP_FPS, fps)
        return

    if resolutions is None:
        resolutions = probe_resolutions(device)
    if not resolutions:
        return

    if fps is None:
        # performance mode: smallest resolution, driver-maximum frame rate
        _resize(device, *resolutions[0])
        return

    # quality mode: largest resolution that achieves the target frame rate.
    # Iterate from largest to smallest; stop at the first resolution where
    # the driver confirms it can deliver at least 90 % of the target fps.
    for w, h in reversed(resolutions):
        _resize(device, w, h)
        device.set(cv2.CAP_PROP_FPS, fps)
        if device.get(cv2.CAP_PROP_FPS) >= fps * 0.9:
            return
    # fallback: all iterations set the smallest resolution last; fps is
    # already requested on the device, clamped to whatever the driver allows.


def _deviceID(device) -> str:
    '''Return the identifier that the system gives a ``QCameraDevice``.

    Qt6 with GStreamer prefixes a path with ``v4l2://``; the prefix is
    removed, so that ids look alike on every Qt backend.
    '''
    text = bytes(device.id()).rstrip(b'\x00').decode(errors='replace')
    return text.removeprefix('v4l2://')


class QOpenCVDevices:
    '''Camera discovery and format enumeration for OpenCV cameras.

    Uses :class:`QtMultimedia.QMediaDevices` when available to enumerate
    cameras and their supported formats without opening the device.  Falls
    back to trial-and-error probing via OpenCV when QtMultimedia is not
    present.

    All methods are static — this class is a namespace, not instantiated.
    '''

    @staticmethod
    def devices(probe: bool = True) -> list[CameraDevice]:
        '''Return the available cameras, with their identifiers.

        The *index* of each is the *cameraID* that OpenCV opens it by.
        OpenCV gives no names and numbers the cameras as its backend does,
        so QtMultimedia names them and the index is worked out for each
        platform (see :meth:`_ordered`).  Without QtMultimedia the cameras
        are found by opening each index in turn, and have no name or id.

        Parameters
        ----------
        probe : bool
            Whether to open each index in turn when there is no
            QtMultimedia.  That opens every camera, even if only for a
            moment: ``False`` returns an empty list instead, for code that
            has a camera open and wants only its name.

        Returns
        -------
        list[CameraDevice]
            One for each camera, sorted by index.
        '''
        if _QMediaDevices is None:
            if not probe:
                return []
            return [CameraDevice(i, name, '')
                    for i, name in QOpenCVDevices._probe_cameras()]
        return [CameraDevice(i, dev.description(), _deviceID(dev))
                for i, dev in QOpenCVDevices._ordered(
                    _QMediaDevices.videoInputs())]

    @staticmethod
    def cameras() -> list[tuple[int, str]]:
        '''Return a list of available cameras as ``(index, name)`` pairs.

        The index is the integer *cameraID* suitable for passing to
        :class:`~QVideo.cameras.OpenCV.QOpenCVCamera`.  See
        :meth:`devices` for the identifiers.

        Returns
        -------
        list[tuple[int, str]]
            ``(cameraID, description)`` for each detected camera, sorted
            by *cameraID*.
        '''
        return [(d.index, d.name) for d in QOpenCVDevices.devices()]

    @staticmethod
    def find(spec: int | str) -> int | None:
        '''Return the index of the camera that *spec* names, or ``None``.

        Parameters
        ----------
        spec : int or str
            An index; the identifier of a device (``CameraDevice.id``, not
            case sensitive); or a part of its name (not case sensitive),
            which must belong to one camera only.

        Returns
        -------
        int or None
            The *cameraID* for OpenCV, or ``None`` if no camera matches, or
            if a part of a name matches two cameras.
        '''
        devices = QOpenCVDevices.devices()
        if isinstance(spec, int):
            return spec if any(d.index == spec for d in devices) else None
        text = str(spec).strip().lower()
        if not text:
            return None
        exact = [d for d in devices if d.id.lower() == text]
        if len(exact) == 1:
            return exact[0].index
        named = [d for d in devices if text in d.name.lower()]
        return named[0].index if len(named) == 1 else None

    @staticmethod
    def _ordered(devices) -> list[tuple[int, object]]:
        '''Return ``(index, device)`` for the devices that Qt lists.

        The order of Qt is not the order of OpenCV: Qt lists the devices
        as the system found them, which depends on when each was plugged
        in.  OpenCV numbers them by rules of its own.

        - Linux: the index is the *N* of the device ``/dev/videoN``.  A
          device that has no such path cannot be opened by index and is
          left out.
        - macOS: OpenCV sorts the devices by their ``uniqueID``.  (A
          MacBook with a USB camera: Qt listed the built-in camera first,
          and OpenCV opened the USB camera as 0, whose id begins ``0x``,
          before the built-in camera, whose id is a UUID.)
        - Elsewhere: the order of Qt, which is the order of the backend
          when both use the same one.  Not checked.
        '''
        system = platform.system()
        if system == 'Linux':
            found = []
            for dev in devices:
                match = re.search(r'/video(\d+)$', _deviceID(dev))
                if match:
                    found.append((int(match.group(1)), dev))
            return sorted(found, key=lambda pair: pair[0])
        if system == 'Darwin':
            return list(enumerate(sorted(devices, key=_deviceID)))
        return list(enumerate(devices))

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
            The device that OpenCV opens as *cameraID* (see
            :meth:`_ordered`), or ``None`` if there is none.
        '''
        for index, dev in QOpenCVDevices._ordered(devices):
            if index == cameraID:
                return dev
        return None

    @staticmethod
    def _formats_from_device(device) -> list[tuple[int, int, float, float]]:
        '''Extract and deduplicate formats from a
        :class:`~QtMultimedia.QCameraDevice`.

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
            cap = cv2.VideoCapture(i, capture_backend())
            opened = cap.isOpened()
            cap.release()
            if not opened:
                break
            found.append((i, f'Camera {i}'))
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
        cap = cv2.VideoCapture(cameraID, capture_backend())
        try:
            return probe_formats(cap, resolutions) if cap.isOpened() else []
        finally:
            cap.release()
