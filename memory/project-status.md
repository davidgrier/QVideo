---
name: QVideo project status
description: Current test count, recent commits, package structure, and pending tasks
type: project
---

# QVideo Project Status

## Current state (as of 2026-03-22)

- 1140 tests passing (+ 16 subtests)
- Main branch: `main`
- **v3.2.3 tagged and pushed to GitHub** (last release)
- Post-release fix: QDVRWidget layout polish (not yet tagged)
- CI passing on Python 3.10, 3.11, 3.12 (GitHub Actions)
- ReadTheDocs: both `latest` and `stable` builds passing
  - URL: https://qvideo.readthedocs.io
  - Config: `.readthedocs.yaml` (ubuntu-22.04, Python 3.12, `.[docs]`)

## CI configuration

- **Platform**: `QT_QPA_PLATFORM=offscreen` — no X server or xvfb needed
- **System deps**: `libgl1 libegl1 libglib2.0-0 libxkbcommon0`
- **conftest.py**: creates `QApplication` before any test module is imported
- `docs/conf.py`: sets `QT_QPA_PLATFORM=offscreen` for headless autodoc

## Key CI lessons learned

- xvfb + xcb causes fatal SIGABRT (exit 134) on GitHub Actions Ubuntu — use `QT_QPA_PLATFORM=offscreen`
- `QApplication` must be created in `conftest.py` before test collection
- `cv2.getLogLevel`/`setLogLevel` require OpenCV >= 4.5.2; guard with `getattr`
- `pip install -e .` must be run in the same environment as IPython/Python to update `importlib.metadata` version

## v3.2.3 changes (2026-03-21)

### GenICam camera fixes (`cameras/Genicam/_camera.py`)
- `_make_getter`: checks access mode before reading; returns `None` when not readable
- `_register_features`: always creates a setter (dynamic mode check at call time); fixes `ExposureTime` being permanently read-only after `ExposureAuto="Once"` sweep
- `_cleanup()`: sets `self.nodeMap = None` after harvester reset
- `settings` property: excludes lowercase `width`/`height` aliases (prevents "Unsupported property" warnings in tree)
- `cameras/Genicam/__init__.py`: sets `__module__` on exported classes for Sphinx

### GenICam tree fixes (`cameras/Genicam/_tree.py`)
- **Poll timer** (500 ms): `_pollCamera` refreshes all visible node values to pick up autonomous camera-side changes (GainAuto reverting "Once"→"Off", auto-exposure/gain adjustments)
- **`AcquisitionResultingFrameRate` fix**: `_updateLimits()` called before the value loop in `_pollCamera` so float bounds are current before `setValue` — prevents stale-limit clipping
- **Shutdown segfault fix** (three layers):
  1. `_pollTimer.stop` connected to `aboutToQuit` (fires before camera teardown)
  2. `isOpen()` guard at top of `_pollCamera`
  3. `nodeMap = None` in `_cleanup()` (belt-and-suspenders)
- `_handleItemChanges`: returns early when `_ignoreSync=True` (prevents re-entrant updates during poll and sync readback)
- `description()`: guards against `None` root node

### Backend tree fixes
- `QFlirTree`: filters `_DEFAULT_SETTINGS` to keys registered on the camera (fixes "Unknown property" startup warnings)
- `QFlirCamera`: `.. warning::` for Spinnaker 4.3.0.189 `DevClose()` hang bug
- Basler/IDS/MV trees: `camera.setSettings(...)` → `camera.settings = ...`

### UI improvements
- `QCameraTree`: `resizeColumnToContents` + stretch-last-column; `setIndentation(10)` (halves default 20 px, narrows widget for FLIR's long names)
- `QVideoScreen`: `resizeEvent` + deferred `_fitToVideo` slot maintains video aspect ratio in containing window
- `demo.py`, `filterdemo.py`, `QCamcorder.py`: layout stretch factors (screen expands, controls stay natural width)

### Demo refactor
- `FilterDemo` renamed from `Demo` in `filterdemo.py`; now subclasses `Demo` (DRY)
- `-r` (OpenCV resolution selector) and `-h` (help) flags documented in module docstrings

### Sphinx/docs
- `docs/conf.py setup()`: `PythonDomain.note_object` patch suppresses Sphinx 8.x duplicate-object warnings
- `docs/api/dvr.rst`, `docs/api/demos.rst`: expanded with per-module sections
- `#:` attribute doc-comments on all PyQt signals across `lib/`, `dvr/`, `demos/`
- `:doi:` roles → plain URL hyperlinks in `filters/Median.py`, `filters/MoMedian.py`
- Footnote label `[1]` → `[R90]` in `MoMedian.py`; `clickable.py` docstring rewritten in NumPy style

## Post-v3.2.3 changes (2026-03-22)

### QDVRWidget layout polish (`dvr/QDVRWidget.ui`)
- Removed hard-coded `minimumSize` (275×120); minimum now derived from children (176 px)
- Outer `QVBoxLayout` spacing 2 → 6 px; margins 1 → 6 px on all sides
- Added `sizePolicy: Preferred/Preferred` so widget uses available vertical space
- Design-time height updated 150 → 200 px

## Remaining TODO (low priority)

- Python 3.13 classifier in `pyproject.toml` (add `"3.13"` to CI matrix first)
- Publish v3.2.3 to PyPI (currently only pushed to GitHub)

## FLIR/GenICam shutdown hang background

**Root cause**: Spinnaker GenTL producer v4.3.0.189 has a `DevClose()` hang bug.
**Resolution**: Downgrade to Spinnaker GenTL **4.1.0.172** (confirmed by FLIR support).

## Package structure: camera backends

| Flag | Backend | Module |
|------|---------|--------|
| `-b` | Basler (pylon SDK) | `QVideo.cameras.Basler` |
| `-c` | OpenCV | `QVideo.cameras.OpenCV` |
| `-f` | FLIR (Spinnaker SDK via GenICam) | `QVideo.cameras.Flir` |
| `-i` | IDS Imaging | `QVideo.cameras.IDS` |
| `-m` | MATRIX VISION mvGenTLProducer | `QVideo.cameras.MV` |
| `-p` | Raspberry Pi camera | `QVideo.cameras.Picamera` |
| `-r` | OpenCV with resolution selector | `QVideo.cameras.OpenCV` |
| `-v` | Allied Vision VimbaX | `QVideo.cameras.Vimbax` |
| (default) | Noise (no hardware) | `QVideo.cameras.Noise` |

Legacy backends (not in release): `devel/Spinnaker/`, `devel/Spinnaker2/`
