# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [3.2.1] — 2026-03-20

### Fixed
- **`numba` removed from required dependencies** — `numba` was listed as a
  core dependency but is only used in an experimental development file
  (`filters/devel/FastMedian.py`) that is not part of the installed package.
  Removing it eliminates an unnecessary ~200 MB download (LLVM) from every
  `pip install QVideo`.

---

## [3.2.0] — 2026-03-19

### Changed
- **Camera module files renamed** — implementation files in each backend are
  now named `_camera.py`, `_tree.py`, and (for OpenCV) `_resolution_tree.py`
  instead of the old `Q<Name>Camera.py` / `Q<Name>Tree.py` names.  This
  eliminates a class/module name collision where importing a backend module
  via its full dotted path caused Python to overwrite the exported class
  reference in the parent package namespace with the module object.

  The **public API is unchanged** — `from QVideo.cameras.X import Q<Name>Camera`
  continues to work exactly as before.  Only code that imported directly from
  the private module path is affected:

  ```python
  # Old (broken):
  from QVideo.cameras.Noise.QNoiseCamera import QNoiseCamera

  # New (correct, and already the documented form):
  from QVideo.cameras.Noise import QNoiseCamera
  ```

### Added
- **`CONTRIBUTING.md`** — developer guide covering environment setup, test
  conventions, backend and filter authoring, and the pull-request workflow.

### Infrastructure
- GitHub Actions workflows opt into Node.js 24 ahead of the June 2026
  forced migration.

---

## [3.1.0] — 2026-03-19

### Added
- **`QPicamera.fps`** — frame-rate property via `FrameDurationLimits`; pinning
  both elements to the same value locks the sensor to a fixed frame rate.
  `read()` now uses `capture_request()` for improved capture efficiency.
- **`QOpenCVResolutionTree`** — new tree widget that replaces the separate
  `width` / `height` spinboxes with a `"W×H"` drop-down populated by probing
  the hardware at startup.  Falls back to spinboxes when only one resolution
  is available.  Accessible via the `-r` flag in `lib/chooser.py`.
- **`QFPSMeter` and `VideoFilter`** added to `lib.__all__`.

### Tests
- Added 48 tests covering `QBaslerCamera`, `QFlirCamera`, `QIDSCamera`, and
  `QMVCamera` / `QMVSource` (12 tests per backend).  Total: 1138 tests.

### Removed
- All `.py~` editor backup files deleted from the repository.

---

## [3.0.0] — 2026-03-18

### Added
- **`QCamera.registerProperty` / `registerMethod`** — unified registration
  system; subclasses call these in `_initialize` to expose camera parameters.
  The base-class `get`, `set`, and `execute` route through the registry,
  holding `self.mutex` for thread safety.
- **`QCamera.__getattr__`** — attribute-style access to registered properties
  (`camera.fps`, `camera.width`) without declaring explicit Python properties.
- **`QCamera.settings` property** — returns all registered property values as
  a `dict`; the setter applies a dict of values via `set`.
- **`QGenicamCamera`** — rewired to `registerProperty` / `registerMethod`:
  walks the GenICam node tree at initialization and registers every accessible
  feature, with stop/restart logic for protected features encoded in setter
  closures.
- **`QFPSMeter`** — rewritten with a sliding-window algorithm for accurate,
  low-latency frame-rate measurement.
- **`resolutions.py`** — cross-platform camera resolution probing replaces
  the previous static lookup table.
- **`QListCVCameras`** — soft OpenCV dependency with probe fallback.
- **`CLAUDE.md`** — developer guide committed to the repository.
- **`cameras/Basler`** — new GenICam backend for Basler cameras via the
  pylon GenTL producer (`ProducerU3V.cti` / `ProducerGEV.cti`).
- **`cameras/IDS`** — new GenICam backend for IDS Imaging cameras.
- **`cameras/MV`** — new GenICam backend using the MATRIX VISION
  mvGenTLProducer for broad camera compatibility.
- **`QGenicamCamera._findProducer`** — static method that searches
  `GENICAM_GENTL64_PATH` (set by all GenICam SDK installers) for a
  named `.cti` producer file; replaces bundled producer directories.
- **`QGenicamTree._updateValues`** — refreshes read-only GenICam node
  values in the property tree after any property change.
- **`QPicamera`** — rewritten: `cameraID`, `width`, `height` parameters;
  `_probeControls` registers all supported picamera2 controls (exposure,
  gain, brightness, contrast, etc.) with hardware-reported ranges.
- **`QPicameraSource`**, **`QPicameraTree`** — new classes following the
  standard camera backend pattern.
- **Sphinx documentation** — full API docs with autodoc, napoleon,
  intersphinx, and furo theme.
- **`demos/`** — module docstrings; all demos use `choose_camera` for
  consistent camera selection.
- Full test suite: **1050+ tests**, 0 failures, covering all core modules,
  camera backends, filters, DVR, and utilities.

### Changed
- `QCamera._properties` and `._methods` are now dicts (keyed by name) rather
  than lists; `QCameraTree` reads them to auto-build the property tree.
- `QCamera.properties`, `.methods`, and `.settings` are now `@property`
  descriptors; previously some backends shadowed them as plain methods.
- `QGenicamCamera`: removed bespoke `set`, `get`, `execute` overrides;
  removed explicit `width`, `height`, `fps` Python properties; removed
  `__properties`, `__methods`, `__modes` static helpers.  `IString` is now
  registered alongside the other property types.
- `QGenicamCamera.protected` is now a `set` (was a `list`).
- `QOpenCVCamera`: device properties probed at runtime and registered only
  if the hardware supports them.
- `QListCameras`: enforced override contract; fixed signal guard.
- `QCameraTree`: improved coverage; fixed pyqtgraph `DeprecationWarning`.
- `QDVRWidget`: fixed writer close bug, disconnect safety; added `newFrame`
  signal.
- DVR subsystem: consolidated readers/writers; added HDF5 and OpenCV formats.
- `QFilterBank`: fixed `deregister`; improved docstrings and test coverage.
- `chooser.py`: data-driven dispatch, full docstrings and tests.
- `clickable`: PyQt5/PyQt6 compatibility fix.
- Packaging: switched to `setuptools.build_meta`; added explicit
  `package-dir` map; added optional-dependency groups (`genicam`,
  `picamera`, `dev`).

### Removed
- `cameras/Genicam/nodemap.py` — dead code; logic moved into
  `QGenicamCamera` private static methods (now also removed in favour of
  `registerProperty`).
- Exploratory Jupyter notebooks from `cameras/Genicam/` and
  `cameras/Spinnaker/`.
- `lib/QCameraList.py` — superseded by `QListCameras`.
- `cameras/Spinnaker` and `cameras/Spinnaker2` — retired from the released
  package; FLIR cameras are now supported via the GenICam interface
  (`cameras/Flir`).  The Spinnaker backends are preserved in `devel/` for
  reference.

### Fixed
- `QGenicamCamera._initialize`: removed `try/finally` anti-pattern that
  silently swallowed the `self.name` `AttributeError` and left `protected`,
  `_properties`, and `_methods` uninitialised.
- `QGenicamCamera`: `IProperty` union type now defined inside the
  `try` block, preventing `NameError` when `genicam` is not installed.
- `QGenicamSource.__init__`: no longer forwards `*args` to
  `QVideoSource.__init__`.
- `QVideoSource`: fixed frame-rate reporting and thread-safety edge cases.

---

## [2.1.0] and earlier

Initial development at New York University.  Camera backends for OpenCV,
GenICam (Harvesters), FLIR/Spinnaker, and Raspberry Pi.  Core display,
DVR, and filter subsystems.
