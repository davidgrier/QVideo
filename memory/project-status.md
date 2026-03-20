---
name: QVideo project status
description: Current test count, recent commits, package structure, and pending tasks
type: project
---

# QVideo Project Status

## Current state (as of 2026-03-20)

- 1138 tests passing (+ 16 subtests)
- Main branch: `main`
- **v3.2.2 tagged and published to PyPI**
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

## Polish work completed (2026-03-20)

- ✅ `version.py` deleted; `QVideo.__version__` via `importlib.metadata`
- ✅ Broken Sphinx directives in `docs/api/cameras.rst` fixed
- ✅ Module docstrings added to all 14 `lib/` modules (single-quote style)
- ✅ `__all__` unified to split-string form across all 9 camera backends
- ✅ `numba` removed from required dependencies and `autodoc_mock_imports`
- ✅ `.gitignore`: added `devel/` and `.claude/`
- ✅ ReadTheDocs configured and badge added to README
- ✅ CLAUDE.md: single quotes preferred; documentation toolchain and NYU theme choices recorded
- ✅ PyData Sphinx Theme with NYU brand colours (`docs/_static/nyu.css`)
- ✅ `QVideo.demos` added to pyproject.toml packages (fixes blank Demos page on RTD)
- ✅ Copyright `2026, David G. Grier` added to `docs/conf.py`
- ✅ Stale `templates_path` removed from `docs/conf.py` (fixed blank left sidebar)

## Remaining TODO (low priority)

- Python 3.13 classifier in `pyproject.toml` (add `"3.13"` to CI matrix first)

## Package structure: camera backends

| Flag | Backend | Module |
|------|---------|--------|
| `-b` | Basler (pylon SDK) | `QVideo.cameras.Basler` |
| `-c` | OpenCV | `QVideo.cameras.OpenCV` |
| `-f` | FLIR (Spinnaker SDK via GenICam) | `QVideo.cameras.Flir` |
| `-i` | IDS Imaging | `QVideo.cameras.IDS` |
| `-m` | MATRIX VISION mvGenTLProducer | `QVideo.cameras.MV` |
| `-p` | Raspberry Pi camera | `QVideo.cameras.Picamera` |
| `-v` | Allied Vision VimbaX | `QVideo.cameras.Vimbax` |
| (default) | Noise (no hardware) | `QVideo.cameras.Noise` |

Legacy backends (not in release): `devel/Spinnaker/`, `devel/Spinnaker2/`
