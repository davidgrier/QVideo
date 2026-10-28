# QVideo — Future Work

Ideas for upgrades and extensions, in no particular order.

---

## Resolution and Region of Interest

Camera resolution changes are a common pain point, especially for
scientific cameras that support a large range of sensor modes.

- **ROI selection GUI** — interactive rectangle drawn on the live
  `QVideoScreen` that the user drags to the desired region; a
  "Set ROI" action crops the sensor (or the downstream frame) to
  match.  Cameras that support hardware ROI (width/height/offsetX/offsetY
  via GenICam `OffsetX`/`OffsetY`/`Width`/`Height`) would apply the crop
  in firmware; others would crop in software.
- **Resolution selector for scientific cameras** — `QOpenCVResolutionTree`
  already probes and lists supported resolutions for OpenCV cameras.
  Extend the concept to GenICam backends: enumerate valid
  `Width`×`Height` combinations at initialization and present them as a
  drop-down (or a grouped tree node) rather than exposing raw integer
  spinboxes.
- **Binning and decimation controls** — many scientific cameras expose
  `BinningHorizontal`/`BinningVertical` GenICam nodes.  Detect and
  register these automatically in `QGenicamCamera` so they appear in
  the tree and interact correctly with the ROI spinboxes.
- **Resolution presets** — common aspect-ratio presets (full sensor,
  half, quarter, 1:1 crop, user-defined) accessible from a single
  drop-down to streamline switching during an experiment.
- **Linked width/height spinboxes** — when the camera requires width and
  height to change together (e.g. square ROI for FFT), enforce the
  constraint in the tree widget rather than silently clamping values.

---

## New Camera Backends

QVideo currently supports OpenCV, GenICam (Basler, FLIR, IDS, MATRIX VISION,
Allied Vision VimbaX), and Raspberry Pi cameras.  Requested and candidate
additions:

- **Hamamatsu** — at least one user has requested Hamamatsu support.
  Hamamatsu cameras are controlled via the `DCAM-API` SDK, wrapped in
  Python by the [`dcamapi4-py`](https://github.com/nstone8/dcamapi4-py)
  or [`pyDCAM`](https://github.com/HamamatsuPhotonics/pyDCAM) packages.
  Implement `QHamamatsuCamera` / `QHamamatsuSource` / `QHamamatsuTree`
  following the standard backend pattern.  DCAM-API exposes properties
  through an integer-keyed property map; `registerProperty` calls
  would enumerate the readable/writable subset at initialization.
- **Andor (SDK3)** — widely used sCMOS and EMCCD cameras in
  single-molecule and fluorescence microscopy labs.  Andor's SDK3
  Python bindings (`pyandor` / `atcore`) follow a similar property-map
  pattern to DCAM-API.
- **Thorlabs (Zelux / Kiralux)** — Thorlabs scientific CMOS cameras
  are controlled via the `thorlabs_tsi_sdk` Python package.
- **PCO** — PCO cameras use the `pco` Python package, which wraps
  the PCO SDK and exposes properties as a dict-like interface.
- **Azure Kinect / Intel RealSense** — depth + color cameras useful
  for 3-D tracking experiments; would add a `depth` frame type
  alongside the existing `Image` type alias.
- **Aravis** — [Aravis](https://github.com/AravisProject/aravis) (LGPL-2.1)
  is an open-source C library for GigE Vision and USB3 Vision cameras.
  Version 0.9.0 (May 2025) introduced an experimental GenTL producer
  `.cti`; the stable 0.8.x series does not yet include it.  Once the
  0.9.x GenTL producer stabilizes, add a `cameras/Aravis` backend (or
  extend `_findProducer` to locate the Aravis `.cti`) to give users a
  fully open-source, zero-cost path to GigE and USB3 cameras without
  a vendor SDK.  The Aravis simulated camera is also a candidate for
  use in CI tests as an alternative to the existing `cameras/Noise`
  reference implementation.
- **GenICam catch-all** — any camera shipping with a GenTL producer
  `.cti` file can already be used via `cameras/MV`.  Improve
  `_findProducer` to search additional standard paths
  (`GENICAM_GENTL32_PATH`, vendor-specific environment variables)
  and document the generic GenICam entry point more prominently.

---

## Unified Camera Discovery and Selection

QVideo has per-backend listing widgets (`QListCVCameras`, `QListFlirCameras`,
etc.) but no single surface that enumerates all available cameras regardless
of backend.

- **`QListCameras` unified API** — a single class (or factory function) that
  queries every installed backend and returns a flat list of
  `(backend, cameraID, display_name)` tuples.  Back-ends that are not
  installed or whose hardware is absent should be silently skipped so the
  caller never needs to guard against missing SDK imports.
- **`QCameraChooser` widget** — a `QComboBox` (or tree view) populated from
  the unified list.  Selecting an entry instantiates the matching
  `Q<Backend>Camera` and `Q<Backend>Source` via the existing `chooser.py`
  dispatch table, returning a ready-to-use source to the parent widget.
  Should replace the current CLI flag approach (`-b/-c/-f/…`) with a
  point-and-click workflow.
- **Integration with `QCamcorder`** — replace the startup camera argument
  with an optional embedded `QCameraChooser` panel so the user can switch
  cameras without restarting the application.

---

## Hot-Plug Support  **Planned; not urgent**

A camera that is unplugged during a session is not handled: the read
warnings flood the log (deliberately, until this is built) and the live
view freezes.  The design recovers inside the capture thread that
`QVideoSource` already owns, so no change to how cameras open is needed
for reconnection, and every change is additive (fits a minor release).

- **Detection** — a camera is lost after `lossTimeout` seconds (default 2)
  without a frame; a backend may report it at once with `self.lost(reason)`.
  The source then stops calling `read()`, which ends the warning flood.
- **State machine** — `QVideoSource` goes `running -> lost -> reconnecting
  -> running` and emits `lost(str)`, `reconnecting(int)` and
  `reconnected()`.  Reconnection closes the camera (guarded: Spinnaker 4.3
  hung in `DevClose`), then reopens it at a back-off interval until the
  user stops the source.
- **Identity and settings** — the camera records its identity (serial
  number, else model and index) and reconnects only to the same device;
  `QCamera.set` keeps the values applied so far, which the source replays
  after a reconnect.
- **Consumers** — the screen keeps the last frame and shows a "camera
  lost" notice; `QCameraTree` is disabled while lost; `QRecorder` stops
  with "camera lost" (`stopWhenLost=True`); `QCamcorder` shows the reason
  in the status bar.
- **Backends** — OpenCV reopens the same index; Genicam/FLIR must
  rediscover (`update()`) and create the same serial again, with a close
  that cannot block; Picamera is not hot-pluggable.
- **Phases** — (0) Noise `unplug()`/`plug()` and a conformance group for
  surviving loss; (1) the state machine and the consumers, tested with
  Noise; (2) OpenCV, tried on a USB webcam; (3) FLIR rediscovery, tried on
  the camera; (4) optional: starting with no camera and discovering new
  devices (OS notifications or polling), which needs the camera to open
  on a worker thread and is the only route back to a splash screen.
- **Open decisions** — reconnect to the same camera only (recommended) or
  any of the same model; stop recording on loss (recommended) or let HDF5
  continue; notice on the screen or status bar only; retry forever
  (recommended) or give up; replay settings (recommended) or camera
  defaults.

---

## Analysis Overlays

The new `overlays/` package provides `QTrackpyWidget` and `QYoloWidget`.
Potential additions:

- **`QLorentzMieWidget`** — feed live frames to `pylorenzmie` for
  in-situ holographic characterization (particle radius, refractive
  index); overlay fitted parameters on `QVideoScreen`.
- **`QBlobWidget`** — lightweight blob detector (OpenCV
  `SimpleBlobDetector`) as a zero-dependency alternative to trackpy
  for quick particle counting.
- **`QFaceWidget`** — face / landmark detection overlay using
  MediaPipe or dlib; useful for human-factors and gaze-tracking demos.

---

## Screen() API and Composable Vision Pipelines

`Camera()` (`interactive/camera.py`) already proves the "minimal code" factory
pattern works well for QVideo: discover a backend, return something
usable immediately, and — in Jupyter — stay awaitable/interactive.
Two follow-on ideas from a 2026-07-10 discussion, in increasing order
of ambition.

### `Screen()` — a display counterpart to `Camera()`

`_CameraProxy.live_view()` already solves the hard part of this in
miniature: it streams JPEG-encoded frames into an `ipywidgets.Image`
via an `asyncio` background task, with no `QVideoScreen`/Qt widget and
no `QApplication` event loop involved. That capability is currently
trapped as a method on the camera proxy — you can only view what
`Camera()` opened.

- **Factor it into a standalone `Screen(source)`** accepting any
  `QCamera`, `QVideoSource`, or `_CameraProxy` — anything with the
  `newFrame`/`fps` duck type `QVideoScreen.source` already accepts
  (see [[project_viewbox_range_bug]]). Lets you view a filtered
  pipeline, DVR playback, or a composited overlay feed, not just a
  raw camera.
- **Environment-dependent implementation**, mirroring the
  `IPython.get_ipython()` check `_CameraProxy._select()` already does:
  - **Jupyter notebook** — `ipywidgets.Image` + `asyncio` task, same
    mechanism as `live_view()`. This works because `ipykernel` runs a
    single persistent `asyncio` event loop that drives both cell
    execution and any background task scheduled on it — the
    frame-update loop keeps running between cells without blocking.
  - **IPython terminal** — a real `QVideoScreen` widget kept live via
    IPython's `%gui qt` input-hook (the same mechanism that makes
    interactive `matplotlib` work), if the user has that integration
    enabled.
  - **Plain script / `python` REPL** — no persistent event loop and
    no input-hook mechanism exists here, and Qt widgets must be
    created/touched on the main thread (strictly enforced on macOS),
    so there is no clean way to get a live-updating display *and* a
    responsive prompt at the same time. Falls back to the traditional
    blocking `screen.show(); app.exec()`.
  - **Takeaway:** "watch video while still typing commands" is a
    genuine capability, but it is a Jupyter-notebook-kernel property
    (or an IPython-terminal-with-`%gui qt` property), not something
    `Screen()` can generalize to every command line.

### Composable pipelines: `Camera() -> Filter() -> Screen(overlay=...)`

Prompted by `Screen()`: could a full vision system — camera, filter
chain, live display, detection overlay — be assembled in a few lines,
the way `Camera()` already assembles a camera in one? The pieces
mostly already exist; what's missing is a thin factory layer over
them:

- **`Filter()` factory, analogous to `Camera()`/`Screen()`** — this is
  now `QFilterPipeline` (`lib/QFilterPipeline.py`): it wraps a source (and
  optionally a `QFilterRack`), filters on a worker thread, and
  re-emits `newFrame(ndarray, FrameInfo)` with `.fps` and `.shape`, so
  it feeds a `Screen()` or a DVR in turn.  A public
  `Filter(source, *filters)` would be a one-line convenience over it.
- **`Screen(source, overlay=...)`** — construct the requested overlay
  widget (`QYoloWidget`, `QTrackpyWidget`, ...), wire
  `overlay.source = source`, and call
  `screen.addOverlay(overlay.overlay)` automatically instead of the
  multi-line manual wiring every demo currently repeats.
- **The real obstacle: overlay rendering is Qt-only today.**
  `QYoloOverlay`/`QTrackpyOverlay` draw via
  `pyqtgraph.GraphicsObject.paint()` (a `QPainter` call) — that only
  works inside a real `QVideoScreen` widget. The Jupyter/`live_view()`
  path JPEG-encodes a bare numpy frame with no `QPainter` involved, so
  `overlay=` can't work there without either (a) a second,
  numpy/`cv2`-based rendering path per overlay (e.g. `cv2.rectangle`
  for `QYoloOverlay`), or (b) reusing the existing
  `QWidget.grab()`-based compositing machinery from
  [[project_overlay_feature2]] (`QVideoScreen._renderComposite`) to
  rasterize the live Qt screen + overlay into an image before
  streaming it to `ipywidgets.Image` — which still requires a real
  (if invisible) `QVideoScreen`/`QApplication` to exist even in the
  Jupyter case, unlike the current pure-`ipywidgets` `live_view()`.
- **Optional sugar, secondary to the factory-call form above:**
  operator overloading (e.g. `cam | GaussianFilter() | Screen()`) for
  a more pipeline-like feel. Worth considering only once the plain
  `Screen(Filter(cam, ...), overlay=...)` factory composition is
  solid — avoid the overload sugar becoming the first thing that has
  to be designed.

### Filters emit results; overlays subscribe instead of detecting

Today `QYoloWidget`/`QTrackpyWidget` connect to `source.newFrame`
directly and run their own detection, independent of whatever
`QFilterPipeline` is doing. That's a latent
correctness gap: if a display filter crops or geometrically
transforms the frame, the overlay's boxes are computed in raw-source
coordinates but drawn on top of a transformed frame. It also
duplicates work — `overlays/yolo.py`'s `_YoloWorker` is a hand-rolled
`QThread` + drop-frame implementation of the latest-wins handoff that
`QFilterPipeline` now provides.

Proposed fix: move detection into a filter stage — e.g.
`YOLOFilter(VideoFilter)` sitting in the rack, pass-through on
the image, emitting a results signal — so detection runs on the frame
*as it exists at that point in the pipeline*, staying correctly
aligned with what's actually displayed, and one inference pass can
feed the overlay, the planned [[project_analysis_writer]]
(`QAnalysisWriter`), and a live stats readout simultaneously instead
of each running its own detector.

- **No base-class change needed.** `QVideoFilter` widgets are
  `QObject` subclasses; a filter's widget can declare its own
  `Signal` directly (`YOLOFilter.detectionsReady = QtCore.Signal
  (object)`) with zero changes to the shared base. Baking a results
  signal into `VideoFilter` itself would be the
  wrong call — those classes back nearly every filter in the project,
  and only detector-style filters (YOLO, Trackpy, maybe a future
  blob/DNN filter) ever need one; the other dozen-plus filters
  (Gaussian, threshold, gamma, ...) would carry a signal they never
  use.
- **A small opt-in convention still helps the registration side.**
  The overlay needs to find "the YOLO filter" in the rack and connect
  to it without special-casing every filter class by name. That only
  needs a consistent signal name (`resultsReady`) or a tiny marker
  mixin (`class ResultsFilter: resultsReady = QtCore.Signal(object)`)
  that just `YOLOFilter`/`TrackpyFilter` additionally inherit from —
  additive and opt-in, not a change to `VideoFilter`.
- **Registration/enable API needed on `QFilterRack`** — the overlay
  needs to find-or-create the detector filter instance by name/type,
  connect to its results signal, and enable it if it isn't already
  active; if the user later disables or removes that filter from the
  rack, the overlay needs to notice and clear its drawn results rather
  than show stale boxes.
- **Migration cost:** a real refactor of two shipped widgets
  (`QYoloWidget`, `QTrackpyWidget`) plus their tests.  A slow detector
  would run on the pipeline's single worker thread and set the pace of
  every later filter, so a detector probably wants its own pipeline.
- **Natural pairing with the YOLO `cv2.dnn` test case** above — worth
  designing the filter/signal split and the torch-free backend
  together rather than migrating YOLO twice.

---

## Remote display and control: an iPad as the instrument panel

Idea (2026-10-26): watch and steer an experiment from an iPad over Wi-Fi.
A native iOS port is not practical: PySide6 runs on iOS only since Qt 6.12
and is early, and there are no iOS builds of OpenCV, `psutil` or `h5py`.
iOS also cannot load a GenTL `.cti` producer or reach USB3 Vision and GigE
cameras, so only UVC webcams would work.  Keep the camera and the
acquisition on the host and make the iPad a client in its browser.

- **Expected display rate**, estimated from JPEG sizes measured on a Mac
  (8-bit gray, OpenCV quality 95; not yet measured over Wi-Fi): 640x480 is
  88 KB per frame, 21 Mbit/s at 30 fps; 1280x720 is 217 KB, 51 Mbit/s;
  1920x1080 is 498 KB, 117 Mbit/s.  Quality 80 needs a half to a third of
  that.  A good Wi-Fi 5 or 6 link sustains 100-400 Mbit/s, so expect a
  steady 20-30 fps up to 1080p, and a delay of about 60-150 ms from sensor
  to screen.  That suits watching and steering, not a feedback loop, which
  stays on the host.  Faster than 30-60 fps needs a video codec (H.264 or
  HEVC over WebRTC), not JPEG.
- **`Camera.live_view` is not built for a network.**  It sets an
  `ipywidgets.Image` every 1/30 s and sends each frame through the Jupyter
  connection as base64, without asking whether the client kept up, so on a
  slow link the picture falls behind in time instead of dropping frames.
- **A streaming component**: the camera keeps its full hardware rate and
  only the display is limited; send the newest frame only (the idea of
  `QFrameRelay`) and wait for the client to acknowledge before sending the
  next; binary frames over a WebSocket, or MJPEG over HTTP, with the size
  and quality chosen to fit the link; overlays (particle markers, an ROI)
  sent as data and drawn by the client; controls through the existing
  property interface.
- **To do first**: prototype the stream and measure it on David's network
  with an iPad, comparing 720p and 1080p and qualities 80 and 95.

---

## DVR Enhancements

- **Metadata sidecar** — write a JSON file alongside each recording
  containing camera settings, frame rate, and timestamps so recordings
  are self-describing without opening the HDF5 file.
- **Playback speed control** — the DVR player currently plays at
  real time; add a rate spinbox for slow-motion and fast-forward review.
- **Delivered frame rate: settled on a FLIR camera (2026-10-27).**
  `QCamera.actualFps` (4.7.0) is the rate that a camera delivers, beside
  `fps`, the rate that was asked for, and `QVideoSource.fps` reports it.
  `QGenicamCamera` reads `AcquisitionResultingFrameRate` (then the older
  names) and falls back to `fps`.  On the FLIR camera the node is the
  delivered rate, not the maximum: 32.640 against 32.63 measured, and
  13.039 against 13.04 measured with a 2.5-frame exposure.  With
  `AcquisitionFrameRateEnable` off the camera free-runs and
  `AcquisitionFrameRate` is read-only and does not follow the exposure, so
  `fps` alone would mislead; no change to `actualFps` is needed.  Not
  tested: whether the node falls when the camera's buffers overrun, and
  whether a request above the maximum is clamped (it needs the frame-rate
  enable).  OpenCV cameras use the rate that the driver reports; QVideo
  does not measure it (decided 2026-10-26).  The file header ignores the
  interval setting (`nskip`) on purpose: recording every Nth frame plays N
  times faster, a time-lapse (decided 2026-10-27); transcode to change it.
---

## PyQt6 Support  **Done** (v3.4.x)

- ~~`conftest.py` direct `from PyQt5.QtWidgets import QApplication`~~ — replaced
  with `from pyqtgraph.Qt import QtWidgets` so the test suite is binding-agnostic.
- ~~`PyQt5` / `PyQt5-sip` hard core dependencies~~ — moved to an optional `pyqt5`
  extra; `pyqt6 = ["PyQt6"]` extra added.  Users choose their binding at install
  time; the package itself makes no assumption.
- ~~DVR icons (`icons_rc_qt6.py`)~~ — the misnamed C file was removed; `icons_rc.py`
  already imports through `pyqtgraph.Qt` and uses the version-3 resource format,
  so it works with both bindings unchanged.
- ~~Enum scoping~~ — the codebase already used fully-scoped enums throughout.
- ~~CI matrix~~ — PyQt6 / Python 3.12 job added alongside the three PyQt5 jobs.

---

## Reduce Core Dependencies  **Done**

- ~~`pandas`~~ — already in the `overlays` optional group.
- ~~`h5py`~~ — already in the `dvr` optional group.
- ~~`PyQt5`/`PyQt5-sip`~~ — already optional (`pyqt5` / `pyqt6` extras).
- **`opencv-python`** — too pervasive to make optional (camera backend,
  DVR writer/reader, filters, resolution probing).  Accepting
  `opencv-python-headless` as an alternative is not yet possible via
  PEP 508; document as a note for headless deployments if requested.

---

## Testing and Quality

- **Hardware-in-the-loop tests** — optional test suite (skipped when
  hardware is absent) that exercises real cameras to catch
  driver-specific regressions.
- **Performance benchmarks** — track frame-drop rate and latency across
  commits for high-frame-rate cameras.

---

## Documentation Gaps

Some pages of the ReadTheDocs site are API listings with little prose.
Fill the gaps so that a page gives a user enough context to use the module
without reading the source.

- **Camera backends** (`docs/api/cameras.rst`) — an introductory paragraph
  per backend covering the target hardware, the SDK prerequisites, the
  install command, and a minimal usage snippet.
- **DVR** (`docs/api/dvr.rst`) — describe the recording formats (HDF5 with
  timestamps and lossless compression; video files written by PyAV or
  OpenCV, and the codec each one uses), the `.newFrame` / `.fps`
  duck-typing contract, and a short wiring example.
- **Overlays** (`docs/api/overlays.rst`) — add a paragraph covering
  `QVideoScreen.composite` and composite-frame recording.

---

## Broken PyPI Page Graphic

The image on the QVideo PyPI page fails to render.  PyPI serves
`README.md` as the project description but does not resolve relative
image paths or GitHub-hosted raw URLs that require authentication.

- Identify the broken `![…](…)` reference in `README.md`.
- Replace the path with an absolute `https://raw.githubusercontent.com/…`
  URL pointing to the `main` branch so PyPI can fetch it directly.
- Verify the fix locally with `twine check dist/*` (renders the long
  description and flags broken markup) before the next release.

---

## Distribution

- Add references to relevant literature in `README.md` (holographic
  video microscopy, particle tracking, YOLO object detection).
- Conda-forge recipe for users who prefer conda environments.

---

## OpenCV 5 Feature Adoption

OpenCV 5 improves property setting (see the platform-specific capture
backend selection added in `cameras/OpenCV/_camera.py`).  Findings from
a full-codebase review (session 2026-07-10):

- ~~**Propagate the per-platform backend fix to all `VideoCapture`
  call sites.**~~  **Done.**  `capture_backend()` in `_devices.py`
  factors out the four-way `CAP_V4L2` / `CAP_MSMF` / `CAP_AVFOUNDATION`
  / `CAP_ANY` platform match and is now reused by `_camera.py`,
  `_devices.py::_probe_formats`, `_devices.py::_probe_cameras`, and
  `QListCVCameras.py::_probe_cameras`.
- ~~**`VideoCapture.get()` now returns `-1` for unsupported
  properties**~~  **Done.**  `_camera.py::_probeProperties` now skips
  a property without attempting `set()` when `get()` returns a
  negative value, except `exposure`, which is exempted because V4L2
  reports it on a log2 scale where legitimate values are themselves
  negative.
- **Lower priority / cosmetic**, no action needed yet:
  - Python bindings now accept keyword arguments broadly
    (`cv2.fn(threshold=0.5)`) — could clean up the more
    parameter-heavy calls in `threshold.py`, `exposure.py`,
    `artistic.py`.
  - `warpAffine`/`remap` interpolation was revised for accuracy in
    5.x — affects `dejitter.py`'s `cv2.warpAffine` call; output will
    shift slightly (not a bug), relevant only if chasing bit-exact
    reproducibility across OpenCV versions.
  - Redesigned DNN engine / ~80% ONNX coverage doesn't apply yet:
    `overlays/yolo.py` uses `ultralytics` directly, not `cv2.dnn`.
    OpenCV 5.0 shipped 2026-06-04 with ONNX operator coverage jumping
    from ~22% to ~80%, and the dev environment is now actually on
    `cv2==5.0.0` (confirmed `cv2.dnn.readNet`,
    `cv2.dnn.ENGINE_AUTO`/`ENGINE_NEW`/`ENGINE_ORT`,
    `cv2.dnn.NMSBoxes` all present). A YOLOv8/v11 `.onnx` export now
    loads directly via `cv2.dnn.readNet(...)`, giving a genuinely
    torch-free detection path — see [[project_opencv5_yolo_research]].
    Not yet prototyped against QVideo's `_YoloWorker`; would need
    manual output decoding + `cv2.dnn.NMSBoxes` in place of
    `ultralytics`' built-in postprocessing.
  - No legacy C API (`CvMat`/`IplImage`/`cv2.cv`) usage anywhere in
    the codebase — confirmed by grep, so the biggest OpenCV 5
    breaking change doesn't touch QVideo at all.
  - `numpy`/`opencv-python` are both unpinned in `pyproject.toml`, so
    NumPy 2.x support in OpenCV 5 needs no dependency-constraint
    action.

---

## OpenCV DNN Framework — New Capabilities

OpenCV 5.0 (released 2026-06-04) rewrote the `cv2.dnn` engine and
raised ONNX operator coverage from ~22% to ~80% (see "OpenCV 5
Feature Adoption" above). The dev environment is confirmed on
`cv2==5.0.0`. Survey of what this opens up for QVideo, roughly
ordered by value vs. effort — see
[[project_opencv5_yolo_research]] for the research behind this list:

- **Torch-free YOLO backend (test case — start here)** — see below.
- **Face/landmark detection with zero extra dependencies** —
  `cv2.FaceDetectorYN` (the YuNet model, `cv2.dnn` under the hood,
  Apache-2.0) as the implementation for the planned `QFaceWidget`
  (see "Analysis Overlays") instead of MediaPipe or dlib.
- **Learned segmentation as a `QForegroundEstimator` option** — an
  ONNX segmentation model (U-Net/DeepLabV3-style) alongside the
  existing classical MOG2 method, selectable per use case.
- **Super-resolution filter** — `cv2.dnn_superres`
  (EDSR/FSRCNN/ESPCN/LapSRN) as a new `VideoFilter` for upscaling
  feeds from low-res USB cameras.
- **Text/OCR overlay** — `cv2.dnn_TextDetectionModel` /
  `TextRecognitionModel` (EAST + CRNN) to read burned-in timestamps,
  instrument displays, or labels in the field of view.
- **Monocular depth estimation** — a lightweight MiDaS-style ONNX
  model as a software fallback pseudo-depth overlay where dedicated
  depth hardware (Kinect/RealSense, see "New Camera Backends") isn't
  available.
- **VLM/natural-language frame captioning** — OpenCV 5 bundles VLM
  support (Qwen 2.5, PaliGemma, etc.); a "describe this frame" widget
  could auto-annotate recordings or flag notable events during
  long unattended acquisitions.
- **Anomaly/novelty detection** — a small autoencoder-style ONNX
  model flagging frames that deviate from a learned baseline; pairs
  with the hot-plug / long-duration-recording themes above.
- **Foundational: shared `DNNFilter`/`QDNNOverlay` base class**
  — wraps `cv2.dnn.Net` (model loading, `blobFromImage`
  preprocessing, `ENGINE_AUTO` selection, a postprocessing hook).
  Every item above needs the same boilerplate; one abstraction
  avoids duplicating it across filters.  Worth building this first if
  more than one DNN-backed filter is planned.

### Test case: torch-free YOLO via `cv2.dnn`

`overlays/yolo.py`'s `_YoloWorker` currently hard-requires
`ultralytics`, which pulls in `torch` — the heaviest optional
dependency in the project. Goal: add a `cv2.dnn`-based backend as a
**second option alongside** the existing `ultralytics` path, not a
replacement, and write up detailed instructions so users can prepare
their own ONNX exports. Findings so far:

- **Keep `torch`/`ultralytics` as an opt-in accelerated backend.**
  OpenCV 5's new DNN engine is CPU-only at launch (its hardware
  acceleration is CPU-side: Intel IPP/AVX, Arm KleidiCV, Qualcomm
  FastCV, RISC-V RVV). Real GPU acceleration for `cv2.dnn`
  (`DNN_BACKEND_CUDA`) requires building OpenCV from source with CUDA
  — the standard `opencv-python`/`opencv-python-headless` pip wheels
  don't include it. `torch`'s pip wheels bundle CUDA (and Apple MPS)
  out of the box. So `cv2.dnn` should be the lightweight default;
  `ultralytics`/`torch` remains the answer for users who have an
  NVIDIA GPU and want maximum throughput.
- **Reimplementation work needed:** `ultralytics`'s Python API does
  box decoding, confidence filtering, and NMS internally.  A
  `cv2.dnn` path needs to redo that manually with
  `cv2.dnn.NMSBoxes` plus manual decoding of the YOLO output tensor
  layout — which differs between YOLO versions/export conventions,
  so the decoding logic must be pinned to a specific export
  convention and documented as such.
- **Do not bundle a `yolov11n.onnx` file in the QVideo repo or
  package as a default fallback.** Ultralytics licenses all
  pretrained YOLO checkpoints (including exports derived from them)
  under AGPL-3.0 by default; their own license page states that using
  the models obligates releasing the complete corresponding source of
  "the larger application" under AGPL-3.0 unless the user holds an
  Ultralytics Enterprise license. That is a materially stronger
  copyleft obligation than QVideo's own GPL-3.0-or-later, and
  redistributing the weights as a bundled default could pull
  downstream users — especially commercial ones — into those terms
  without them realizing it. Also a plain repo-hygiene concern:
  bundling a binary model blob conflicts with the "media files belong
  only under `docs/`" / no-build-step / small-footprint conventions
  already in place (see "Reduce Core Dependencies").
  Alternatives to write into the user instructions instead:
  - Auto-download-on-first-use from a canonical source (mirroring
    what `ultralytics.YOLO(model_name)` already does), caching
    locally, with a clear notice of the AGPL-3.0 terms and a pointer
    to Ultralytics' Enterprise licensing page for commercial users
    who need to avoid them.
  - Document how a user exports their own `.onnx` from a YOLO
    checkpoint they already have rights to use (`torch` is required
    for the one-time export step even though it's not needed at
    inference time — "torch-free" applies to runtime, not model
    preparation).
  - Investigate whether the [OpenCV Zoo](https://github.com/opencv/
    opencv_zoo) has a permissively-licensed (Apache-2.0) general
    object-detection model suitable as a truly redistributable
    default, separate from anything YOLO/Ultralytics-derived.

---

## Scale-aware scrolling of spinbox values  **Done**

- ~~pyqtgraph implements the dec property for SpinBox, which scales
  the step size according to the order of magnitude of the value.
  This would be helpful for camera properties such as exposure time
  that can range over several orders of magnitude. Consider how to
  implement this feature.~~ `QCameraTree._updateStep` recomputes each
  float parameter's step to ~10% of its current magnitude whenever
  the value changes (tree edit, camera echo-back, or programmatic
  `set()`), instead of `dec=True`'s coarse whole-power-of-ten jumps.
  Applies to every float property in any `QCameraTree`, not just
  GenICam — generalizes the adaptive-step precedent already used in
  `QGenicamTree`.
