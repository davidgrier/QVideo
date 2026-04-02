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
- **Azure Kinect / Intel RealSense** — depth + colour cameras useful
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

## Reduce Core Dependencies

The current core install requires `h5py`, `opencv-python`, and `pandas`
even for users who only want basic camera display with no DVR, no filters,
and no overlays.  Moving niche packages to optional groups lowers the
barrier to entry and avoids pulling in large binary wheels unnecessarily.

Candidates for optional groups:

- **`pandas`** — used only by `overlays/trackpy.py` and `overlays/yolo.py`
  to carry detection results.  Move to an `overlays` optional group.
  Both modules currently import pandas unconditionally at the top level;
  they would need to adopt the project's soft-import pattern
  (`try: import pandas as pd / except ImportError: pd = None`) and emit
  a helpful error message when a user enables the overlay without pandas
  installed.
- **`h5py`** — used only by `dvr/HDF5Writer.py` and `dvr/HDF5Reader.py`.
  Move to a `dvr` optional group.  The DVR widget already falls back
  gracefully to OpenCV video formats when `h5py` is absent at runtime;
  the dependency can simply be removed from the core list.
- **`opencv-python`** — pervasive (OpenCV camera backend, DVR video
  writer/reader, several filters, resolution probing), so it cannot
  easily be made fully optional.  However, `opencv-python` ships a heavy
  GUI build; consider accepting `opencv-python-headless` as an alternative
  for server / headless deployments by loosening the requirement to
  `opencv-python | opencv-python-headless` (PEP 508 `or` syntax not yet
  widely supported, but achievable via extras or documentation note).
- **`PyQt5` / `PyQt5-sip`** — see PyQt6 section above; these should
  become optional once the binding abstraction is complete.

Suggested revised dependency structure:

```toml
dependencies = ["numpy", "pyqtgraph"]

[project.optional-dependencies]
pyqt5    = ["PyQt5", "PyQt5-sip"]
pyqt6    = ["PyQt6"]
dvr      = ["h5py", "opencv-python"]
overlays = ["pandas"]
genicam  = ["harvesters", "genicam"]
picamera = ["picamera2"]
full     = ["QVideo[pyqt5,dvr,overlays,genicam]"]
dev      = ["QVideo[pyqt5,dvr,overlays]", "pytest", "pytest-cov"]
```

---

## Testing and Quality

- **Hardware-in-the-loop tests** — optional test suite (skipped when
  hardware is absent) that exercises real cameras to catch
  driver-specific regressions.
- **Performance benchmarks** — track frame-drop rate and latency across
  commits for high-frame-rate cameras.

---

## Distribution

- Add references to relevant literature in `README.md` (holographic
  video microscopy, particle tracking, YOLO object detection).
- Conda-forge recipe for users who prefer conda environments.
