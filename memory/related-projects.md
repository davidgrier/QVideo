---
name: Related camera/lab-instrument projects
description: Python projects with capabilities similar to QVideo — for reference, comparison, or future integration ideas
type: reference
---

# Projects Similar to QVideo

## Closest in scope

- **pylablib** — broad lab instrument support including cameras (Andor, Thorlabs, PCO, etc.) with a similar hardware-abstraction pattern. More instrument-focused than camera-focused; no Qt UI layer. https://pylablib.readthedocs.io/

- **instrumental-lib** — Python bindings for lab hardware including cameras. Similar goals to pylablib but less actively maintained.

## GenICam / acquisition layer only (no Qt UI)

- **Harvesters** — what QVideo uses internally for GenICam acquisition. Pure acquisition, no threading or UI. https://github.com/genicam/harvesters

- **egrabber** (Euresys) — GenICam acquisition library, commercial/SDK-specific.

## Microscopy-oriented

- **python-microscope** — device abstraction for microscopy hardware including cameras; no Qt UI, focused on remote/programmatic control. https://python-microscope.org/

- **pymmcore / pymmcore-plus** — Python bindings for Micro-Manager, which has enormous hardware support through its device adapter ecosystem. `pymmcore-plus` adds a more Pythonic API. Most serious overlap with QVideo's goals; heavier due to Micro-Manager's Java heritage. https://pymmcore-plus.readthedocs.io/

- **napari** — image viewer with a plugin ecosystem; camera acquisition via plugins rather than built-in. https://napari.org/

## QVideo's differentiators

- Lightweight pure-Python/PyQt5 stack — no Java, no C++ build step
- `QCameraTree` auto-generates a Qt control panel from `registerProperty` calls — no per-camera UI code needed
- Clean separation of hardware, threading, and UI layers
