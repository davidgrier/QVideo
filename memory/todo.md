---
name: QVideo TODO list
description: Concrete deficiencies identified in polish assessment (2026-03-20)
type: project
---

# QVideo TODO

## High priority

### Version files stuck at 3.0.0
- `version.py` line 3: `__version__ = '3.0.0'` → should be `'3.2.1'`
- `docs/conf.py` line 14: `release = '3.0.0'` → should be `'3.2.1'`
- These should be kept in sync with `pyproject.toml` on every release.
  Consider reading version dynamically from pyproject.toml via
  `importlib.metadata.version('QVideo')` in both files.

### Broken Sphinx directive
- `docs/api/cameras.rst` line 34: `.. automodule:: QVideo.cameras.OpenCV.QOpenCVResolutionTree`
  This references a non-existent module path (it was renamed to `_resolution_tree`).
  Fix: remove the line or replace with `.. automodule:: QVideo.cameras.OpenCV._resolution_tree`

## Medium priority

### Missing module docstrings in lib/
Sphinx autodoc cannot generate module-level summaries without module docstrings.
All 14 files below have class/function docstrings but no module-level docstring:
- `lib/QCamera.py`
- `lib/QCameraTree.py`
- `lib/QFPSMeter.py`
- `lib/QFilterBank.py`
- `lib/QListCameras.py`
- `lib/QVideoReader.py`
- `lib/QVideoScreen.py`
- `lib/QVideoSource.py`
- `lib/QVideoWriter.py`
- `lib/VideoFilter.py`
- `lib/chooser.py`
- `lib/clickable.py`
- `lib/resolutions.py`
- `lib/types.py`

## Low priority

### Missing Python 3.13 classifier in pyproject.toml
`requires-python = ">=3.10"` already allows 3.13, but there is no explicit
`"Programming Language :: Python :: 3.13"` classifier. Add once CI is tested
on 3.13 (add `"3.13"` to the matrix in `test.yml` first).

### Inconsistent `__all__` formatting in camera backends
- Noise, Genicam, Flir, Vimbax, OpenCV use: `'QXxxCamera QXxxSource QXxxTree'.split()`
- Basler, IDS, MV, Picamera use: `['QXxxCamera', 'QXxxSource', 'QXxxTree']`
Standardize to one form across all nine backends.

### No test file for lib/types.py
`lib/types.py` is the only lib module without a corresponding test file.
It is a small module (type aliases only), but a `test_types.py` would
complete coverage.
