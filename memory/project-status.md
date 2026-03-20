---
name: QVideo project status
description: Current test count, recent commits, package structure, and pending tasks
type: project
---

# QVideo Project Status

## Current state (as of 2026-03-19)

- 1138 tests passing (+ 16 subtests)
- Main branch: `main`
- **v3.2.0 tagged and published to PyPI**
- CI passing on Python 3.10, 3.11, 3.12 (GitHub Actions)
- Codecov integration active; coverage badge in README.md

## Recent commits (post-v3.2.0 CI fixes)

| Hash | Description |
|---|---|
| `086c7bf` | Guard cv2.getLogLevel/setLogLevel with getattr for older OpenCV |
| `1a323d7` | Switch CI from xvfb/xcb to QT_QPA_PLATFORM=offscreen |
| `c47fafc` | Add conftest.py to create QApplication before test collection |
| `d6099ff` | Fix CI crash: create QApplication before importing chooser module |
| `d87b116` | (v3.2.0 release commit) |

## CI configuration (current)

- **Platform**: `QT_QPA_PLATFORM=offscreen` — no X server or xvfb needed
- **System deps**: `libgl1 libegl1 libglib2.0-0 libxkbcommon0` (xcb/xvfb packages removed)
- **conftest.py**: creates `QApplication` before any test module is imported (prevents SIGABRT)
- **Coverage**: uploaded to Codecov from Python 3.10 job only; badge in README.md
- **Codecov token**: stored as `CODECOV_TOKEN` GitHub repo secret

## Key CI lessons learned

- xvfb + xcb causes fatal SIGABRT (exit 134) in GitHub Actions Ubuntu — use `QT_QPA_PLATFORM=offscreen` instead
- `QApplication` must be created in `conftest.py` (before test collection), not inside individual test files, because pytest collects `test_chooser.py` first and importing pyqtgraph tree widgets before QApplication exists triggers the abort
- `cv2.getLogLevel`/`setLogLevel` require OpenCV >= 4.5.2; guard with `getattr`

## Release checklist (completed)

- ✅ License changed MIT → GPL v3
- ✅ pyproject.toml: authors, keywords, classifiers, [project.urls]
- ✅ GitHub Actions: test.yml (3.10/3.11/3.12) and publish.yml in place
- ✅ All backend files renamed _camera.py/_tree.py (eliminates class/module name collision)
- ✅ CONTRIBUTING.md added
- ✅ Codecov coverage badge in README.md
- ✅ PyPI project-scoped API token stored as `PYPI_API_TOKEN` GitHub secret
- ✅ v3.2.0 successfully published to PyPI

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
