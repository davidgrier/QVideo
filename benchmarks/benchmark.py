#!/usr/bin/env python3
'''Measure how fast QVideo moves, filters and records frames.

Four benchmarks, run one at a time or all but the camera::

    python benchmarks/benchmark.py                 # capture, filters, record
    python benchmarks/benchmark.py capture
    python benchmarks/benchmark.py filters
    python benchmarks/benchmark.py record
    python benchmarks/benchmark.py camera -c       # a live camera (flags of
                                                   # any QVideo program)

``capture``
    A synthetic camera at a steady rate feeds a
    :class:`~QVideo.lib.QVideoSource` and a consumer on the GUI thread.
    Reports the frames per second that arrive, the delay from the moment the
    camera returns a frame to the moment that the GUI thread has it, the
    CPU that the process uses, and the frames that were dropped (gaps in
    the frame index).
``filters``
    The time that each filter needs for one frame of 1280 x 720 gray and
    1920 x 1080 color, with its default settings.
``record``
    The frames per second that each file writer sustains and how much it
    compresses, for frames of noise (the worst case for a lossless codec)
    and for a smooth scene with a little noise.
``camera``
    The ``capture`` measurement for a camera that is attached.

``--csv DIRECTORY`` saves the tables and a description of the machine, so
that a result can be compared with another.  Every number depends on the
machine, the Python, the Qt binding and the libraries, which are printed
first.
'''
import argparse
import os
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from qtpy import QtCore, QtWidgets  # noqa: E402
import qtpy  # noqa: E402

from QVideo.lib import QCamera, QVideoSource  # noqa: E402
from QVideo.lib.videotypes import FrameInfo  # noqa: E402

__all__ = ['machine', 'measure', 'benchmarkFilters', 'benchmarkRecord']


# ----------------------------------------------------------------------
# the machine
# ----------------------------------------------------------------------

def machine() -> dict[str, str]:
    '''Describe the computer and the software that the numbers belong to.'''
    from importlib.metadata import PackageNotFoundError, version

    def versionOf(name: str) -> str:
        try:
            return version(name)
        except PackageNotFoundError:
            return 'not installed'

    cpu = platform.processor() or platform.machine()
    if sys.platform == 'darwin':
        import subprocess
        done = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'],
                              capture_output=True, text=True)
        cpu = done.stdout.strip() or cpu
    elif Path('/proc/cpuinfo').exists():
        for line in Path('/proc/cpuinfo').read_text().splitlines():
            if line.startswith('model name'):
                cpu = line.split(':', 1)[1].strip()
                break
    return {
        'QVideo': versionOf('QVideo'),
        'Python': platform.python_version(),
        'System': f'{platform.system()} {platform.release()}',
        'CPU': f'{cpu} ({os.cpu_count()} threads)',
        'Qt binding': f'{qtpy.API_NAME} {qtpy.QT_VERSION}',
        'OpenCV': cv2.__version__,
        'NumPy': np.__version__,
        'PyAV': versionOf('av'),
        'h5py': versionOf('h5py'),
    }


# ----------------------------------------------------------------------
# tables
# ----------------------------------------------------------------------

def show(title: str, rows: list[dict]) -> None:
    '''Print *rows*, dictionaries with the same keys, as a table.'''
    print(f'\n{title}\n{"-" * len(title)}')
    if not rows:
        print('(nothing to show)')
        return
    columns = list(rows[0])
    cells = [[str(row[column]) for column in columns] for row in rows]
    widths = [max(len(column), *(len(cell[i]) for cell in cells))
              for i, column in enumerate(columns)]
    print('  '.join(c.ljust(w) for c, w in zip(columns, widths, strict=True)))
    for cell in cells:
        print('  '.join(t.ljust(w) for t, w in zip(cell, widths, strict=True)))


def save(directory: Path, name: str, rows: list[dict]) -> None:
    '''Write *rows* to ``name.csv`` in *directory*.'''
    if not rows:
        return
    directory.mkdir(parents=True, exist_ok=True)
    columns = list(rows[0])
    lines = [','.join(columns)]
    lines += [','.join(str(row[c]).replace(',', ';') for c in columns)
              for row in rows]
    (directory / f'{name}.csv').write_text('\n'.join(lines) + '\n')


# ----------------------------------------------------------------------
# capture
# ----------------------------------------------------------------------

class PacedCamera(QCamera):

    '''A camera that returns a new copy of one frame at a steady rate.

    The frames come at absolute deadlines, so a late frame does not delay
    the ones after it.  A real camera makes a new array for every frame,
    and so does this one.
    '''

    def __init__(self, shape: tuple[int, ...], fps: float) -> None:
        super().__init__()
        self._frame = np.random.default_rng(0).integers(
            0, 256, shape, dtype=np.uint8)
        self._interval = 1. / fps
        self._deadline = 0.
        self.registerProperty('fps', getter=lambda: 1. / self._interval,
                              setter=None, ptype=float)
        self.open()

    def _initialize(self) -> bool:
        self._deadline = time.perf_counter()
        return True

    def _deinitialize(self) -> None:
        pass

    def read(self) -> QCamera.CameraData:
        self._deadline += self._interval
        delay = self._deadline - time.perf_counter()
        if delay > 0:
            time.sleep(delay)
        return True, self._frame.copy()


class Probe(QtCore.QObject):

    '''Counts the frames that leave the capture thread and reach the GUI.'''

    def __init__(self) -> None:
        super().__init__()
        self.latencies: list[float] = []
        self.indices: list[int] = []

    @QtCore.Slot(np.ndarray, object)
    def deliver(self, frame: np.ndarray, info: FrameInfo) -> None:
        '''Runs on the GUI thread, through a queued connection.'''
        self.latencies.append(time.perf_counter() - info.timestamp)
        self.indices.append(info.index)


def measure(camera: QCamera, seconds: float = 3.,
            settle: float = 0.5) -> dict:
    '''Run *camera* through a source for *seconds* and report how it went.

    Parameters
    ----------
    camera : QCamera
        An open camera.
    seconds : float
        How long to measure, after *settle* seconds that are not counted.
    settle : float
        Time for the first frames and the threads to settle.

    Returns
    -------
    dict
        ``fps`` delivered to the GUI thread, ``p50 ms`` and ``p99 ms`` of
        the delay from capture to the GUI thread, ``cpu %`` (of one core,
        for the whole process) and ``dropped`` frames.
    '''
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    source = QVideoSource(camera)
    probe = Probe()
    source.newFrame.connect(probe.deliver,
                            QtCore.Qt.ConnectionType.QueuedConnection)
    marks: dict[str, float] = {}

    def begin() -> None:
        probe.latencies.clear()
        probe.indices.clear()
        marks['t'] = time.perf_counter()
        marks['cpu'] = time.process_time()

    def finish() -> None:
        marks['t1'] = time.perf_counter()
        marks['cpu1'] = time.process_time()
        app.quit()

    source.start()
    QtCore.QTimer.singleShot(int(settle * 1000), begin)
    QtCore.QTimer.singleShot(int((settle + seconds) * 1000), finish)
    app.exec()
    source.stop()
    source.wait(5000)

    elapsed = marks['t1'] - marks['t']
    latency = np.array(probe.latencies) * 1e3
    indices = probe.indices
    dropped = (indices[-1] - indices[0] + 1 - len(indices)) if indices else 0
    return {
        'fps': round(len(indices) / elapsed, 1),
        'p50 ms': round(float(np.percentile(latency, 50)), 2)
        if latency.size else None,
        'p99 ms': round(float(np.percentile(latency, 99)), 2)
        if latency.size else None,
        'cpu %': round(100 * (marks['cpu1'] - marks['cpu']) / elapsed),
        'dropped': dropped,
    }


#: What the capture benchmark runs: (frame shape, frame rates).
CAPTURE = (((480, 640), (30, 100, 300, 1000)),
           ((1024, 1280), (30, 100, 300)),
           ((1080, 1920, 3), (30, 60, 120)))


def benchmarkCapture(seconds: float) -> list[dict]:
    '''Run the synthetic cameras of :data:`CAPTURE`.'''
    rows = []
    for shape, rates in CAPTURE:
        size = f'{shape[1]}x{shape[0]}' + (' color' if len(shape) > 2
                                            else ' gray')
        mbytes = np.prod(shape) / 2**20
        for fps in rates:
            print(f'  capture {size} at {fps} fps ...', flush=True)
            camera = PacedCamera(shape, fps)
            result = measure(camera, seconds)
            camera.close()
            rows.append({'frame': size, 'MB/frame': round(mbytes, 2),
                         'requested fps': fps, **result})
    return rows


# ----------------------------------------------------------------------
# filters
# ----------------------------------------------------------------------

def benchmarkFilters(repeats: int = 9) -> list[dict]:
    '''Time every filter of :mod:`QVideo.filters` on two frame sizes.'''
    import inspect
    import QVideo.filters as filters
    from QVideo.lib.QVideoFilter import VideoFilter
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    rng = np.random.default_rng(0)
    frames = {'720p gray': rng.integers(0, 256, (720, 1280), np.uint8),
              '1080p color': rng.integers(0, 256, (1080, 1920, 3), np.uint8)}

    def median(function, frame) -> float:
        for _ in range(2):
            function(frame)
        times = []
        for _ in range(repeats):
            start = time.perf_counter()
            function(frame)
            times.append((time.perf_counter() - start) * 1e3)
        return statistics.median(times)

    rows = []
    for name in sorted(filters.__all__):
        cls = getattr(filters, name)
        if not (inspect.isclass(cls) and issubclass(cls, VideoFilter)
                and cls is not VideoFilter):
            continue
        if name.startswith('Q') and issubclass(cls, QtWidgets.QWidget):
            continue
        row: dict = {'filter': name, '720p gray ms': None,
                     '1080p color ms': None, 'note': ''}
        try:
            function = cls()
            gray = frames['720p gray']
            # a filter may learn the first frames, so try several
            trials = [np.roll(gray, 37 * i, axis=0) for i in range(5)]
            if all(np.array_equal(function(x), x) for x in trials):
                row['note'] = 'default settings change nothing'
            for label, frame in frames.items():
                row[label + ' ms'] = round(median(function, frame), 2)
        except Exception as error:
            row['note'] = type(error).__name__
        rows.append(row)
    return rows


# ----------------------------------------------------------------------
# recording
# ----------------------------------------------------------------------

def scene(shape: tuple[int, int]) -> np.ndarray:
    '''Return a smooth, microscope-like frame with a little noise.'''
    rng = np.random.default_rng(1)
    h, w = shape
    y, x = np.mgrid[0:h, 0:w]
    image = 90 + 60 * np.exp(-(((x - w / 2) / (w / 3)) ** 2
                               + ((y - h / 2) / (h / 3)) ** 2))
    image = image + rng.normal(0, 2, shape)
    return np.clip(image, 0, 255).astype(np.uint8)


def benchmarkRecord(nframes: int = 200) -> list[dict]:
    '''Time the file writers of :mod:`QVideo.dvr.formats`.'''
    from QVideo.dvr import formats
    from QVideo.dvr.QOpenCVWriter import QOpenCVWriter
    shape = (1024, 1280)
    contents = {'noise': np.random.default_rng(2).integers(
                    0, 256, shape, dtype=np.uint8),
                'scene': scene(shape)}
    cases: list[tuple[str, type, str, dict]] = []
    if formats.h5py_available:
        from QVideo.dvr.QHDF5Writer import QHDF5Writer
        cases += [('HDF5, no compression', QHDF5Writer, '.h5',
                   {'compression': None}),
                  ('HDF5, lzf', QHDF5Writer, '.h5', {'compression': 'lzf'}),
                  ('HDF5, zstd', QHDF5Writer, '.h5', {'compression': 'zstd'})]
    if formats.pyav_available:
        from QVideo.dvr.QPyAVWriter import QPyAVWriter
        cases += [('PyAV FFV1 (lossless)', QPyAVWriter, '.mkv', {}),
                  ('PyAV H.264', QPyAVWriter, '.mp4', {})]
    cases += [('OpenCV (lossless .avi)', QOpenCVWriter, '.avi', {})]
    raw = np.prod(shape) * nframes / 2**20
    rows = []
    with tempfile.TemporaryDirectory() as directory:
        for label, cls, suffix, options in cases:
            for content, frame in contents.items():
                print(f'  record {label}, {content} ...', flush=True)
                path = Path(directory) / f'bench{suffix}'
                path.unlink(missing_ok=True)
                writer = cls(str(path), fps=30, nframes=nframes, **options)
                start = time.perf_counter()
                for index in range(nframes):
                    writer.write(frame, FrameInfo(index, time.perf_counter()))
                writer.close()
                elapsed = time.perf_counter() - start
                size = path.stat().st_size / 2**20 if path.exists() else 0.
                rows.append({'writer': label, 'frames': content,
                             'fps': round(nframes / elapsed, 1),
                             'MB/s': round(raw / elapsed),
                             'file MB': round(size, 1),
                             'ratio': round(raw / size, 2) if size else None})
    return rows


# ----------------------------------------------------------------------
# a live camera
# ----------------------------------------------------------------------

def benchmarkCamera(argv: list[str], seconds: float) -> list[dict]:
    '''Measure the camera that the flags in *argv* name.'''
    from QVideo.cameras.chooser import open_camera, camera_parser
    parser = camera_parser(argparse.ArgumentParser())
    sys.argv = [sys.argv[0], *argv]
    key, camera = open_camera(parser)
    print(f'  camera: {key}, {camera.shape} ...', flush=True)
    try:
        result = measure(camera, seconds)
    finally:
        camera.close()
    return [{'camera': key, 'frame': str(camera.shape), **result}]


# ----------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__.split('\n')[0],
        epilog='For camera, give the flags of any QVideo program (-c, -f, '
        '-g, ...).')
    parser.add_argument('which', nargs='*', default=[],
                        help='capture, filters, record or camera followed '
                        'by camera flags (default: capture filters record)')
    parser.add_argument('--seconds', type=float, default=3.,
                        help='seconds to measure each capture (default: 3)')
    parser.add_argument('--csv', metavar='DIRECTORY', type=Path,
                        help='save the tables here')
    args, rest = parser.parse_known_args()
    which = args.which or ['capture', 'filters', 'record']
    flags = which[1:] + rest if which[0] == 'camera' else []
    if which[0] == 'camera':
        which = ['camera']
    unknown = [name for name in which
               if name not in ('capture', 'filters', 'record', 'camera')]
    if unknown:
        parser.error(f'unknown benchmark: {", ".join(unknown)}')

    info = machine()
    print('\n'.join(f'{key:11s}{value}' for key, value in info.items()))
    results: dict[str, list[dict]] = {}
    if 'capture' in which:
        results['capture'] = benchmarkCapture(args.seconds)
    if 'filters' in which:
        results['filters'] = benchmarkFilters()
    if 'record' in which:
        results['record'] = benchmarkRecord()
    if 'camera' in which:
        results['camera'] = benchmarkCamera(flags, args.seconds)
    titles = {'capture': 'Capture: synthetic camera to the GUI thread',
              'filters': 'Filters: time for one frame',
              'record': 'Recording: 200 frames of 1280 x 1024 gray',
              'camera': 'Camera'}
    for name, rows in results.items():
        show(titles[name], rows)
        if args.csv:
            save(args.csv, name, rows)
    if args.csv:
        (args.csv / 'machine.txt').write_text(
            '\n'.join(f'{k}: {v}' for k, v in info.items()) + '\n')
        print(f'\nSaved in {args.csv}')


if __name__ == '__main__':  # pragma: no cover
    main()
