# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run all tests
python -m pytest

# Run a single test file
python -m pytest tests/test_qgenicamcamera.py

# Run a single test
python -m pytest tests/test_qgenicamcamera.py::TestRead::test_frame_shape

# Run with coverage report
python -m pytest --cov=. --cov-report=term-missing

# Build HTML documentation  (output: docs/_build/html/index.html)
sphinx-build -b html docs docs/_build/html
```

No build step is required. The package is used directly from the source tree.

## Releasing

When pushing a new version, always create a GitHub Release (not just a tag) so
that Zenodo's webhook fires and mints a DOI:

```bash
git tag vX.Y.Z && git push origin vX.Y.Z
gh release create vX.Y.Z --title "vX.Y.Z" --generate-notes
```

Pushing the tag alone is not sufficient — Zenodo listens for the GitHub
`release` event, not a raw tag push.

## Architecture

QVideo is a Qt framework — compatible with PyQt5, PyQt6, and PySide — for integrating scientific cameras into research applications. The design separates hardware communication, threading, property introspection, and UI into distinct layers.

### Core abstractions (`lib/`)

**`QCamera`** is the abstract base for all cameras. Subclasses implement three methods:
- `_initialize() -> bool` — open the device, call `registerProperty` / `registerMethod` for every adjustable parameter, return success
- `_deinitialize()` — release the device
- `read() -> (bool, ndarray | None)` — capture one frame

`registerProperty(name, getter, setter, ptype, **meta)` stores a property spec in `self._properties` (a dict). The base-class `get` / `set` / `execute` all route through this dict, holding `self.mutex` (a `QMutex`). `__getattr__` delegates attribute access (`camera.fps`) to registered getters, so subclasses do not need explicit Python properties for every camera parameter.

**`QVideoSource`** wraps a camera in a `QThread`, calling `camera.saferead()` in a loop and emitting `newFrame(ndarray)`. It is the standard way to drive a camera from the GUI thread.

**`QCameraTree`** is a `pyqtgraph.parametertree` widget. It reads `camera._properties` to auto-build a control tree — no manual UI code needed per camera. It requires `_properties` to be a proper dict (populated via `registerProperty`).

**`VideoFilter`** / **`QFilterBank`** provide a composable image-processing pipeline that sits between a source and a display widget.

### Camera backends (`cameras/`)

Each backend lives in its own subdirectory and follows the same pattern:
- `Q<Name>Camera` — subclasses `QCamera`
- `Q<Name>Source` — subclasses `QVideoSource`, wraps the camera
- `Q<Name>Tree` — subclasses `QCameraTree` if extra UI logic is needed
- `__init__.py` exports all three

Hardware-specific packages (`harvesters`/`genicam` for GenICam, `PySpin` for Spinnaker) are soft dependencies: the import is wrapped in `try/except (ImportError, ModuleNotFoundError)`. Any module-level names derived from those imports must also be inside the `try` block (not after it).

**`cameras/Noise`** is the reference implementation — no hardware required, used as a model for tests and for verifying the framework.

**`cameras/Genicam`** uses the [Harvesters](https://github.com/genicam/harvesters) library and a GenTL producer `.cti` file to communicate with GenICam-compliant cameras. Producer files live in `cameras/Genicam/producer/`. The `protected` list tracks features whose access mode changes after `device.start()` (i.e. features that require stopping acquisition to reconfigure).

### DVR (`dvr/`)

Self-contained recording subsystem. Supports HDF5 (lossless, with timestamps) and OpenCV video formats. `QDVRWidget` is the composite UI widget.

### Filters (`filters/`)

Stateless or stateful image transforms (`QBlurFilter`, `QEdgeFilter`, `QRGBFilter`, `QSampleHold`, etc.). Each subclasses `VideoFilter` and implements `__call__(frame) -> frame`.

## Test conventions

- Tests use `unittest` with `unittest.mock`; each file has a module-level `app` singleton.
- Qt signals are tested with `QtTest.QSignalSpy`.
- Hardware is always mocked — never rely on physical devices in tests.
- For cameras with optional dependencies, inject mock modules into `sys.modules` **before** importing the module under test:
  ```python
  sys.modules.setdefault('harvesters.core', mock_harvesters_core)
  sys.modules.setdefault('genicam.genapi', mock_genapi)
  # ...
  from QVideo.cameras.Genicam.QGenicamCamera import QGenicamCamera
  ```
- **Module vs class name collision**: When a `__init__.py` re-exports a class with the same name as its submodule (e.g. `cameras/Genicam/__init__.py` re-exports `QGenicamCamera`, `cameras/Picamera/__init__.py` re-exports `QPicamera`), both `import QVideo.cameras.X.Y as m` and `patch('QVideo.cameras.X.Y.attr', ...)` resolve to the class, not the module. Use `sys.modules['QVideo.cameras.X.Y']` to get the actual module object, then `patch.object(module, 'attr', ...)`.
- Patch hardware classes with `patch.object(module, 'Harvester', return_value=mock_harvester)`.
- `# pragma: no cover` on all `if __name__ == '__main__':` guards.
- Docstrings use NumPy style.

## Documentation

Sphinx documentation uses the **PyData Sphinx Theme** (`pydata-sphinx-theme`)
with NYU brand colours applied via `docs/_static/nyu.css`:

- Primary: NYU purple `#57068c`
- Accent/hover: NYU violet `#8900e1`

`docs/conf.py` key settings:
- `html_theme = 'pydata_sphinx_theme'`
- `html_static_path = ['_static']` + `html_css_files = ['nyu.css']`
- `html_theme_options`: GitHub URL, `show_toc_level: 2`, theme switcher in navbar
- `os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')` at the top, before any imports, for headless autodoc builds
- `copyright = '2026, David G. Grier'`
- Version read via `importlib.metadata.version('PackageName')`
- Docstrings: NumPy style

ReadTheDocs config (`.readthedocs.yaml`):
- `os: ubuntu-22.04`, `python: '3.12'`
- apt packages: `libgl1 libegl1 libglib2.0-0 libxkbcommon0`
- Install: `pip install -e ".[docs]"`

`[project.optional-dependencies]` docs group: `pydata-sphinx-theme`, `sphinx`, `sphinx-autodoc-typehints`.

Add `html_sidebars = {'**': []}` to suppress the empty left sidebar on leaf pages — the top navbar handles navigation for small sites.

## OpenCV camera configuration

Resolution and format utilities live in `cameras/OpenCV/_devices.py` alongside
`QOpenCVDevices`.  The key functions are `probe_formats`, `probe_resolutions`,
and `configure`.

`QOpenCVCamera` configures resolution and frame rate once at device-open time via
`cameras/OpenCV/_devices.configure()`. Three modes:

- **Quality** (default): `QOpenCVCamera()` — probes supported resolutions, selects
  the largest that achieves ≥ 90 % of the target fps (default 30 fps).
- **Performance**: `QOpenCVCamera(fps=None)` — probes resolutions, selects the
  smallest (maximizes frame rate; slo-mo mode).
- **Explicit**: `QOpenCVCamera(width=W, height=H, fps=F)` — applies values directly
  without probing.

`QOpenCVCamera._initialize()` calls `probe_formats(self.device)` on the already-open
device to discover the actual maximum fps per resolution (by requesting 120 fps and
reading back what the V4L2 driver accepts).  The resulting `_formats` list is stored
on the camera and consumed by `QOpenCVTree` to populate the resolution dropdown.

`width` and `height` are registered as writable properties.  Runtime resolution
changes are applied directly via OpenCV's V4L2 backend, which handles the required
`VIDIOC_STREAMOFF`/`VIDIOC_S_FMT`/`VIDIOC_STREAMON` cycle internally — no device
close or source stop is needed.  `QOpenCVTree` exposes them as read-only display
fields; format changes are made through the `resolution` dropdown, which updates
width, height, and fps atomically.

The `-c` CLI flag opens `QOpenCVTree` in quality mode.

## Style

- Prefer single quotes over double quotes for strings, including docstrings.

## Naming conventions

Follow the PyQt camelCase convention for all instance attributes on Qt classes:
- Use `camelCase` for private attributes (e.g. `self._ignoreSync`, `self._isOpen`, `self._colorCapable`).
- Use `snake_case` only for pure-Python, non-Qt classes (e.g. `VideoFilter` subclasses).
- When renaming, update both the source file and all corresponding test files.
