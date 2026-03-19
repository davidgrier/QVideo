---
name: v3.1.0 TODO list
description: Planned improvements to justify a minor version bump from 3.0.0 to 3.1.0
type: project
---

# v3.1.0 TODO

## Core features

- [x] **QPicamera fps property** — `FrameDurationLimits` registered as `fps`; `capture_request()` used in `read()`
- [x] **QOpenCVResolutionTree** — resolution drop-down selector; `-r` flag in chooser

- [ ] **IRegister node support in QGenicamTree** (`cameras/Genicam/QGenicamTree.py:101`)
      FIXME comment already in place; GenICam register nodes currently absent from control tree

- [ ] **SobelFilter** (`filters/SobelFilter.py`)
      Stub exists as `filters/SobelFilter.py~`; model on `QEdgeFilter` and `QBlurFilter`

- [ ] **QFlirListCameras** (`cameras/Flir/`)
      Camera enumeration widget; partial implementation in `QListFlirCameras.py~`

- [ ] **QListCVCameras** (`cameras/OpenCV/`)
      Camera enumeration widget; partial implementation in `QListCVCameras.py~`
      Follow `QListGenicamCameras` pattern for parity across backends

## Test coverage

- [x] **Tests for QBaslerCamera** (`cameras/Basler/`)
- [x] **Tests for QFlirCamera** (`cameras/Flir/`)
- [x] **Tests for QIDSCamera** (`cameras/IDS/`)
- [x] **Tests for QMVCamera** (`cameras/MV/`)

## Filter promotion from devel/

- [ ] Evaluate `filters/devel/FastMedian.py` — promote if production-ready
- [ ] Evaluate `filters/devel/OMedian.py` — promote if production-ready
- [ ] Evaluate `filters/devel/VMedian.py` — promote if production-ready

## Cleanup

- [ ] Delete all `.py~` backup files throughout the repo
- [ ] Add `QFPSMeter` and `VideoFilter` to `lib/__init__.__all__`
- [ ] Replace account-scoped PyPI token with project-scoped token
