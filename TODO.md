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

## Restore Spinnaker PySpin Backend  **Blocked until June 2026**

The `devel/Spinnaker` and `devel/Spinnaker2` backends use the FLIR PySpin SDK
directly.  They are excluded from the release package pending a fix from FLIR.
Restore and re-integrate once the next FLIR software release (expected June 2026)
resolves the current compatibility issues.

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
  0.9.x GenTL producer stabilises, add a `cameras/Aravis` backend (or
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

## Hot-Plug Support

Camera connections and disconnections during a running session are not
currently handled; the application typically crashes or hangs when a camera
is physically removed.

- **Disconnect detection** — `QVideoSource` should catch the hardware error
  (read failure, exception from `camera.saferead()`) and emit a
  `cameraDisconnected` signal rather than propagating the exception.  The
  source thread should stop gracefully and leave the UI in a recoverable
  state.
- **Reconnect / re-initialize** — after a disconnect signal, the source (or
  a supervising widget) should periodically retry `camera._initialize()` and
  emit `cameraReconnected` once the device is available again, automatically
  resuming the live feed without user intervention.
- **OS-level device notifications** — use `QFileSystemWatcher` (Linux
  `/dev/video*`) or platform device-arrival events (Windows
  `WM_DEVICECHANGE`, macOS IOKit) to trigger discovery when a new camera is
  plugged in, rather than relying solely on read errors to detect changes.
- **GenICam producer events** — Harvesters exposes `on_new_buffer` and
  device-lost callbacks; wire these into the disconnect/reconnect machinery
  so GenICam cameras benefit from the same hot-plug handling as OpenCV
  cameras.
- **UI feedback** — the `QCameraTree` (and `QCameraChooser` above) should
  reflect device state visually: greyed-out controls when disconnected,
  a status indicator, and an optional toast/notification when a camera
  comes back online.

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

`Camera()` (`lib/_camera.py`) already proves the "minimal code" factory
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

- **`Filter()` factory, analogous to `Camera()`/`Screen()`** — wraps
  a `QFilterBank`/`QFilterRack` around a source and re-emits filtered
  frames as a `newFrame`-duck-typed object, so it can feed a
  `Screen()` or a DVR in turn. This already exists in embryonic,
  private form: `demos/filterrackdemo.py::_FilteredSource` connects to
  `source.newFrame`, runs the frame through a `QFilterRack`, and
  re-emits it, exposing `.fps` — promoting this into a public
  `lib/_filter.py::Filter(source, *filters)` would make it reusable
  outside that one demo.
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

---

## DVR Enhancements

- **Metadata sidecar** — write a JSON file alongside each recording
  containing camera settings, frame rate, and timestamps so recordings
  are self-describing without opening the HDF5 file.
- **Circular buffer mode** — keep only the last N seconds in memory
  and flush to disk on a trigger; useful for capturing events
  retrospectively.
- **Playback speed control** — the DVR player currently plays at
  real time; add a rate spinbox for slow-motion and fast-forward review.

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

Many sections of the ReadTheDocs site are stub pages with only
automodule directives and no explanatory prose.  Fill the gaps so each
page gives a user enough context to use the module without reading source.

- **Camera backends** (`basler.rst`, `flir.rst`, `ids.rst`, `mv.rst`,
  `vimbax.rst`, `genicam.rst`, `opencv.rst`, `picamera.rst`, `noise.rst`) —
  introductory paragraph per page covering target hardware, SDK prerequisites,
  install command, and a minimal usage snippet.
- **DVR** — describe the two recording formats (HDF5 with timestamps,
  OpenCV video), the `.newFrame` / `.fps` duck-typing contract, and a short
  wiring example.
- **Filters** — add prose to any filter section that is still directive-only;
  include a pipeline composition example using `QFilterBank`.
- **Overlays** — verify Trackpy and YOLO prose is current; add a paragraph
  covering `QVideoScreen.composite` and composite-frame recording.
- **Architecture** — add a section on the task framework (`lib/tasks/`) and
  a signal-flow sketch from hardware through source, filter bank, screen,
  and DVR.
- **Quickstart page** — a top-level walkthrough from `pip install` to a live
  camera window in fewer than ten lines.  Currently missing entirely.
- **API completeness** — audit every public class and function against the
  existing `automodule` directives; add missing entries to the appropriate
  `.rst` file.

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
- **Foundational: shared `AsyncDNNFilter`/`QDNNOverlay` base class**
  — wraps `cv2.dnn.Net` (model loading, `blobFromImage`
  preprocessing, `ENGINE_AUTO` selection, a postprocessing hook).
  Every item above needs the same boilerplate; one abstraction
  avoids duplicating it the way `AsyncVideoFilter` already does for
  background-thread filters generally. Worth building this first if
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
