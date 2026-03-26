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
- **Azure Kinect / Intel RealSense** — depth + colour cameras useful
  for 3-D tracking experiments; would add a `depth` frame type
  alongside the existing `Image` type alias.
- **GenICam catch-all** — any camera shipping with a GenTL producer
  `.cti` file can already be used via `cameras/MV`.  Improve
  `_findProducer` to search additional standard paths
  (`GENICAM_GENTL32_PATH`, vendor-specific environment variables)
  and document the generic GenICam entry point more prominently.

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
