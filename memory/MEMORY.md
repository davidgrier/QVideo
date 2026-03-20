# QVideo Memory Index

This directory stores persistent notes about the QVideo project for use across Claude Code sessions.

## TODO
See [todo.md](todo.md) for the full deficiency list from the 2026-03-20 polish assessment.

## Files

| File | Contents |
|---|---|
| `architecture.md` | Package structure, repo layout, import collision notes |
| `conventions.md` | camelCase naming convention, renamed attributes, test conventions, soft dependency pattern |
| `genicam.md` | QGenicamCamera-specific notes: stubs, dynamic accessibility, protected list, import collision |
| `project-status.md` | Current test count, recent commits, pending tasks |
| `todo.md` | Deficiency list from 2026-03-20 polish assessment |
| `pypi-publish-guide.md` | Step-by-step guide for publishing to PyPI via GitHub Actions (API token method) |
| `related-projects.md` | Python projects with similar camera/lab-instrument capabilities (pylablib, pymmcore-plus, python-microscope, napari, Harvesters) |

## Quick reference

- Repo root IS the `QVideo` package; parent dir `/Users/davidgrier/python` is on sys.path
- All Qt instance attributes use camelCase (e.g. `_isOpen`, `_colorCapable`, `nodeMap`)
- `device.remote_device.node_map` (Harvesters library) stays snake_case
- `cameras/Genicam/__init__.py` re-exports the class — use `sys.modules[...]` to get the module
- Soft dependencies need full stubs in the `except` branch to avoid NameError at class-eval time
- 1138 tests passing as of 2026-03-19
- v3.1.0 published to PyPI; project-scoped `PYPI_API_TOKEN` secret stored in GitHub repo
