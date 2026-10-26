# QVideo: Qt framework for video cameras

[![PyPI version](https://img.shields.io/pypi/v/QVideo)](https://pypi.org/project/QVideo/)
[![Python](https://img.shields.io/pypi/pyversions/QVideo)](https://pypi.org/project/QVideo/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE.md)
[![Tests](https://github.com/davidgrier/QVideo/actions/workflows/test.yml/badge.svg)](https://github.com/davidgrier/QVideo/actions/workflows/test.yml)
[![Documentation](https://app.readthedocs.org/projects/qvideo/badge/?version=latest)](https://qvideo.readthedocs.io/en/latest/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19239402.svg)](https://doi.org/10.5281/zenodo.19239402)

**QVideo** is a framework for integrating video cameras into Qt projects
(PyQt6 or PyQt5; PySide6 is experimental) for scientific research.  It provides a unified, registration-based property
system so that every camera backend — USB webcams, GenICam devices, FLIR
cameras, Raspberry Pi cameras — is controlled through the same API.  Property
trees, display widgets, and a digital video recorder are built on top of that
abstraction and require no camera-specific code.

<img src="https://raw.githubusercontent.com/davidgrier/QVideo/main/docs/dvrdemo.png" width="75%" alt="QVideo interface demo">

## Features

- **Unified camera API** — `QCamera` subclasses expose adjustable parameters
  via `registerProperty` / `registerMethod`; UI and recording layers consume
  them without knowing the underlying hardware.
- **Auto-built property trees** — `QCameraTree` reads the registered property
  map and builds a `pyqtgraph` parameter tree widget automatically.
- **Threaded video source** — `QVideoSource` wraps any camera in a `QThread`
  and emits `newFrame(ndarray, FrameInfo)` at acquisition rate.
- **Composable filter pipeline** — `VideoFilter` objects run in a
  `QFilterPipeline` on a worker thread between source and consumers (display,
  recorder); filters include blur, edge detection, RGB channel selection,
  sample-and-hold, binary threshold, and blob coloring.
- **Graphical overlays** — `QTrackpyWidget` for live particle tracking and
  `QYoloWidget` for real-time object detection render markers directly on
  `QVideoScreen`; composite mode lets the DVR record the annotated scene.
- **Digital video recorder** — lossless HDF5 (with timestamps) and OpenCV
  video formats; `QDVRWidget` is the composite UI widget.
- **Live display** — `QVideoScreen` supports mouse-aware graphical overlays
  for annotations, regions of interest, and user interaction.

## Installation

```bash
pip install "QVideo[pyqt6]"
```

### Qt binding

QVideo needs a Qt binding: PyQt6 (recommended) or PyQt5.  The binding is
an optional extra so that QVideo can use one you already have, such as the
system packages on a Raspberry Pi, instead of installing a second copy:

```bash
pip install "QVideo[pyqt6]"   # PyQt6 (recommended)
pip install "QVideo[pyqt5]"   # PyQt5
pip install QVideo            # use a binding that is already installed
```

PySide6 is experimental (`pip install "QVideo[pyside6]"`): it runs in
continuous integration, but not all of QVideo's tests have been adapted to it.

### Raspberry Pi

PyPI has no prebuilt ARM wheels for PyQt5 or PyQt6, so the system-provided
packages must be used instead.  Create the virtual environment with
`--system-site-packages` so pip can see them:

```bash
sudo apt install python3-pyqt6 python3-pyqt6.qtsvg
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install QVideo
```

Replace `python3-pyqt6` with `python3-pyqt5` if you prefer PyQt5.

### Optional hardware backends

| Backend | Extra | Notes |
|---------|-------|-------|
| GenICam cameras (Vimba, etc.) | `pip install QVideo[genicam]` | Requires a vendor-supplied `.cti` producer file |
| Raspberry Pi camera | `pip install QVideo[picamera]` | Requires `picamera2` |

## Quick start

```python
import pyqtgraph as pg
from QVideo.cameras.Noise import QNoiseSource
from QVideo.lib import QVideoScreen

pg.mkQApp()

source = QNoiseSource()          # synthetic noise — no hardware needed
screen = QVideoScreen()
source.newFrame.connect(screen.setImage)

screen.show()
source.start()
pg.exec()
```

Replace `QNoiseSource` with `QOpenCVSource`, `QGenicamSource`, etc. to switch
hardware — the rest of the code is identical.

## Camera backends

| Backend | Class | Hardware |
|---------|-------|----------|
| `cameras/Noise` | `QNoiseCamera` | Synthetic — no hardware required |
| `cameras/OpenCV` | `QOpenCVCamera` | USB webcams via OpenCV |
| `cameras/Genicam` | `QGenicamCamera` | Abstract base for all GenICam/GigE Vision cameras |
| `cameras/Flir` | `QFlirCamera` | FLIR cameras via GenICam (Spinnaker GenTL producer) |
| `cameras/Basler` | `QBaslerCamera` | Basler cameras via GenICam (pylon GenTL producer) |
| `cameras/IDS` | `QIDSCamera` | IDS Imaging cameras via GenICam |
| `cameras/MV` | `QMVCamera` | Any GenICam camera via MATRIX VISION mvGenTLProducer |
| `cameras/Vimbax` | `QVimbaXCamera` | Allied Vision cameras via VimbaX GenTL producer |
| `cameras/Picamera` | `QPicamera` | Raspberry Pi camera module |

## Compatibility

Verified on real hardware (the unit tests mock all hardware):

| Backend | macOS | Ubuntu | Raspberry Pi OS | Windows |
|---------|-------|--------|-----------------|---------|
| OpenCV | 14 – 26 | 24.04 | tested | not tested |
| FLIR (GenICam) | 14 – 26 | 24.04 | — | not tested |

On macOS 26.7.1 (Tahoe), the OpenCV backend was tested with OpenCV
5.0.0_11 and the FLIR backend with Spinnaker SDK 4.4.0.246.  Other combinations are expected to work but have not been
checked.  See the [documentation](https://qvideo.readthedocs.io) for
details.

QVideo itself is pure Python and is tested on Python 3.11 – 3.14.  The
newest Python release may lag: Python 3.15 is run in CI as an
allowed-failure job because some dependencies (e.g. scipy) do not yet
publish wheels for it.

## Writing a new camera backend

Subclass `QCamera` and implement three methods:

```python
from QVideo.lib import QCamera

class MyCamera(QCamera):

    def _initialize(self) -> bool:
        self.device = open_my_hardware()
        if not self.device:
            return False
        self.registerProperty('exposure',
                              getter=lambda: self.device.get_exposure(),
                              setter=lambda v: self.device.set_exposure(v),
                              ptype=float)
        return True

    def _deinitialize(self) -> None:
        self.device.close()

    def read(self):
        ok, frame = self.device.read_frame()
        return ok, frame
```

`QCameraTree` and `QVideoSource` work with `MyCamera` immediately — no
additional code needed.

## Filters

| Filter | Class | Description |
|--------|-------|-------------|
| Gaussian blur | `QBlurFilter` | Smoothing with adjustable kernel radius |
| Canny edge detection | `QEdgeFilter` | Edge map with configurable thresholds |
| RGB channel selection | `QRGBFilter` | Pass one or more color channels |
| Sample and hold | `QSampleHold` | Background normalization via a sampled median estimate |
| Binary threshold | `QThresholdFilter` | Convert to binary mask at a configurable level |
| Blob coloring | `QBlobFilter` | Color connected foreground regions with distinct hues |
| YOLO annotation | `QYOLOFilter` | Annotate frames with YOLO bounding boxes (requires `ultralytics`) |

## Overlays

Overlays render analysis results directly on the live `QVideoScreen`.  Each
needs its own optional packages: `pip install QVideo[trackpy]` for the trackpy
overlay, `pip install QVideo[yolo]` for the YOLO overlay (which pulls in
PyTorch), or `pip install QVideo[overlays]` for both.

| Overlay | Class | Description |
|---------|-------|-------------|
| Particle tracking | `QTrackpyWidget` | Live particle detection and tracking using `trackpy` |
| Object detection | `QYoloWidget` | Real-time bounding-box detection using YOLO (`ultralytics`) |

## Acknowledgements

Work on this project at New York University is supported by the National
Science Foundation of the United States under award number DMR-2428983 and
by an award from the TAC Program of New York University.
