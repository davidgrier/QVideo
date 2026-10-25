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

## Media files

Media files (PNG, JPG, GIF, AVI, MP4, etc.) belong only under `docs/`.
Never commit media files to the repo root or any non-docs directory.
`.gitignore` enforces this for new files; already-tracked files outside
`docs/` should be removed with `git rm`.

## Scratchpad directories

Any directory named `devel/` (at any depth) is a local scratchpad and is
excluded from git via `.gitignore`.  These directories exist only on the
developer's machine and must never be committed.

## Releasing

`pyproject.toml` is the single source of truth for the version number.
`__init__.py` and `docs/conf.py` read it via `importlib.metadata` — do not
duplicate it there.  `CITATION.cff` is auto-updated by CI (`.github/workflows/
update-citation.yml`) on tag push — **never edit `CITATION.cff` manually**.

Release steps:

1. Bump `version` in `pyproject.toml` only.
2. Commit and push.
3. Tag and push the tag:

```bash
git tag vX.Y.Z && git push origin vX.Y.Z
```

The tag push triggers two CI workflows automatically:
- `publish.yml` builds the package, publishes to PyPI, **and creates the
  GitHub Release** (do not run `gh release create` manually — it will
  conflict with CI and fail).
- `update-citation.yml` updates `CITATION.cff` and commits it back.

The GitHub Release event fires Zenodo's webhook and mints a DOI.

## Architecture

QVideo is a Qt framework — compatible with PyQt6 and PyQt5 (PySide6 is experimental) — for integrating scientific cameras into research applications. The design separates hardware communication, threading, property introspection, and UI into distinct layers.

**Qt binding.**  A binding is essential but is an optional extra
(`QVideo[pyqt6]` recommended, `[pyqt5]`, `[pyside6]` experimental), never a
hard dependency: pip cannot say "use whichever is installed", and a forced
install would break Raspberry Pi systems that use the system `python3-pyqt*`
packages.  `import QVideo` with no binding raises an `ImportError` naming the
extras.  PySide6 is experimental: the library runs under it, but the tests
use PyQt-style `QtTest.QSignalSpy` (a sequence; PySide6's is not) and
`button.clicked.emit(False)`, so about 80 tests fail there; CI runs PySide6
as an allowed-failure job.  Abstract `QObject` classes use the shared
`QABCMeta` (`lib/_qabc.py`) rather than defining their own metaclass, and
`__setattr__` overrides on `QObject` subclasses must use
`super().__setattr__` (`object.__setattr__` is rejected by Python 3.12 and
earlier under PySide6).

### Core abstractions (`lib/`)

**`QCamera`** is the abstract base for all cameras. Subclasses implement three methods:
- `_initialize() -> bool` — open the device, call `registerProperty` / `registerMethod` for every adjustable parameter, return success
- `_deinitialize()` — release the device
- `read() -> (bool, ndarray | None)` — capture one frame

`registerProperty(name, getter, setter, ptype, **meta)` stores a property spec in `self._properties` (a dict). The base-class `get` / `set` / `execute` all route through this dict. One reentrant lock (`camera._mutex`, a
`threading.RLock`) serializes all device access: `registerProperty` and
`registerMethod` wrap every getter, setter and method in it and `saferead`
holds it per frame, so nothing is read or written during a frame read and
backends need no locking of their own.  The lock is private: code above a
camera never takes it.  A GUI that must poll the hardware asks the camera
for a snapshot (`QGenicamCamera.state`), which is read under the lock. `__getattr__` delegates attribute access (`camera.fps`) to registered getters, so subclasses do not need explicit Python properties for every camera parameter.

**`QVideoSource`** wraps a camera in a `QThread`, calling `camera.saferead()` in a loop and emitting `newFrame(ndarray)`. It is the standard way to drive a camera from the GUI thread.

**`QCameraTree`** is a `pyqtgraph.parametertree` widget. It reads `camera._properties` to auto-build a control tree — no manual UI code needed per camera. It requires `_properties` to be a proper dict (populated via `registerProperty`).

**`VideoFilter`** objects run in a **`QFilterStack`** (a worker thread), optionally driven by a **`QFilterRack`** of filter widgets, between a source and its consumers.

### Camera backends (`cameras/`)

Each backend lives in its own subdirectory and follows the same pattern:
- `Q<Name>Camera` — subclasses `QCamera`
- `Q<Name>Source` — subclasses `QVideoSource`, wraps the camera
- `Q<Name>Tree` — subclasses `QCameraTree` if extra UI logic is needed
- `__init__.py` exports all three

Hardware-specific packages (`harvesters`/`genicam` for GenICam, `PySpin` for Spinnaker) are soft dependencies: the import is wrapped in `try/except (ImportError, ModuleNotFoundError)`. Any module-level names derived from those imports must also be inside the `try` block (not after it).

When adding a new backend, update all four of the following:

1. `lib/_camera.py` — add an entry to `_BACKENDS` (module path, camera class name, tree class name, display label) and append the key to `_DISCOVERY_ORDER` at the appropriate priority position.
2. `lib/chooser.py` — add an entry to `_CAMERAS` with the CLI flag character and help string.
3. `QCamcorder.py` — update the flag list in the module docstring.
4. `demos/__init__.py` — update the flag list in the module docstring.

**`cameras/Noise`** is the reference implementation — no hardware required, used as a model for tests and for verifying the framework.

**`cameras/Genicam`** uses the [Harvesters](https://github.com/genicam/harvesters) library and a GenTL producer `.cti` file to communicate with GenICam-compliant cameras. Producer files live in `cameras/Genicam/producer/`. The `protected` list tracks features whose access mode changes after `device.start()` (i.e. features that require stopping acquisition to reconfigure).

### Applications and demos

(`QCameraTree`) as its first argument.  Its `__main__` block is one call,
(`QCameraTree`) as its first argument.  Its `main()` is one call,
`launch(Class, 'Title')` (`lib/_launch.py`), which chooses the camera from
the command line, shows the window and runs it.  Demos are recipes: each
extension is a short named method, and combining extensions is application
code (see `demos/combineddemo.py`), not a framework feature.

### DVR (`dvr/`)

Self-contained recording subsystem. Supports HDF5 (lossless, with timestamps) and OpenCV video formats. `QDVRWidget` is the composite UI widget.

### Filters (`filters/`)

Stateless or stateful image transforms (`QBlurFilter`, `QEdgeFilter`, `QRGBFilter`, `QSampleHold`, etc.). Each subclasses `VideoFilter` and implements `__call__(frame) -> frame`.

Filters share `QVideo.lib.imageops.grayscale` for color-to-gray conversion
(luminance, RGB ordered, one `cv2.cvtColor`); do not write
`image.mean(axis=2)`, which is about 100 times slower.  Prefer OpenCV calls
and lookup tables (`cv2.LUT`, as in `GammaFilter` and `ExposureFilter`) to
NumPy expressions on whole float images; numba is not used.

Filters are applied by `QFilterStack` (`lib/QFilterStack.py`), a worker thread
between a source and its consumers (screen, DVR, overlays).  It takes
`VideoFilter` objects or a `QFilterRack` (`rack=`), passes the `FrameInfo` of
each frame through unchanged, keeps up to `depth` waiting frames (the default
`depth=1` always processes the newest), removes and reports a filter that
raises, and never touches a widget from the worker thread: the rack hands it
plain `VideoFilter` objects.  Connect consumers to the stack
(`screen.source = stack`), not to the raw source, so they share one filtered
stream.  The screen applies no filters.  A filter overrides `process(frame)`
if it is stateless, or `add`/`get` if it keeps state; none of them owns a
thread.

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
with NYU brand colors applied via `docs/_static/nyu.css`:

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
on the camera, which registers a `resolution` property (a `str` with
`limits`) that `QCameraTree` renders as a dropdown.

`width` and `height` are registered as writable properties.  Runtime resolution
changes are applied directly via OpenCV's V4L2 backend, which handles the required
`VIDIOC_STREAMOFF`/`VIDIOC_S_FMT`/`VIDIOC_STREAMON` cycle internally — no device
close or source stop is needed.  They are registered `hidden` when a
`resolution` property exists, so the tree shows only the `resolution`
dropdown, which updates width, height, and fps atomically.

The `-c` CLI flag opens `QOpenCVTree` in quality mode.

## Style

- Prefer single quotes over double quotes for strings, including docstrings.
- Maximum line length is 79 characters (PEP 8). This applies to all source files: Python, RST, and CLAUDE.md prose lines.
- Use American English spelling in all code, docstrings, comments, documentation, and UI strings: *color* (not colour), *normalize* (not normalise), *center* (not centre), *gray* (not grey), *behavior* (not behaviour), etc.

## Naming conventions

Follow the PyQt camelCase convention for all instance attributes on Qt classes:
- Use `camelCase` for private attributes (e.g. `self._ignoreSync`, `self._isOpen`, `self._colorCapable`).
- Use `snake_case` only for pure-Python, non-Qt classes (e.g. `VideoFilter` subclasses).
- When renaming, update both the source file and all corresponding test files.
