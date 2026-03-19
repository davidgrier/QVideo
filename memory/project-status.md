---
name: QVideo project status
description: Current test count, recent commits, package structure, and pending tasks
type: project
---

# QVideo Project Status

## Current state (as of 2026-03-19)

- 1138 tests passing (+ 16 subtests)
- Main branch: `main`
- **v3.1.0 published to PyPI**: https://pypi.org/project/QVideo/
- Post-3.1.0 work on main (not yet released):
  - CONTRIBUTING.md added
  - GitHub Actions workflows opted into Node.js 24
  - All camera module files renamed from Q<Name>Camera/Tree.py to _camera/_tree.py (Option B collision fix)

## Recent commits (v3.1.0 work)

| Hash | Description |
|---|---|
| (pending) | QOpenCVResolutionTree: resolution drop-down selector for OpenCV cameras |
| (pending) | QPicamera: fps property via FrameDurationLimits; capture_request() for read() |
| `037e010` | Revert to pypa/gh-action-pypi-publish with API token; upgrade pip/build |
| `69cf931` | Change license from MIT to GPL v3 |
| `4bcded4` | Prepare v3.0.0 for PyPI release |

## Release checklist (completed)

- ✅ License changed MIT → GPL v3 (required: PyQt5 is GPL v3)
- ✅ pyproject.toml: authors, keywords, classifiers, [project.urls]
- ✅ pyproject.toml: `license = { text = "GPL-3.0-or-later" }` (SPDX text form avoids License-File metadata issue)
- ✅ README.md: correct slot name, updated camera table, GPL badge
- ✅ CHANGELOG.md: test count 1050+, all new backends documented
- ✅ logging.basicConfig() removed from lib/QVideoWriter.py
- ✅ dvr/__init__.py: duplicate QOpenCVWriter removed
- ✅ __all__ added to all lib/ modules and QCamcorder.py
- ✅ GitHub Actions: test.yml (3.10/3.11/3.12) and publish.yml in place
- ✅ QPicamera rewritten with full property registration and 56 tests
- ✅ Sphinx documentation complete
- ✅ PyPI API token stored as `PYPI_API_TOKEN` GitHub secret
- ✅ v3.0.0 successfully published to PyPI

## Pending tasks

- Replace account-scoped PyPI token with project-scoped token for better security

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
