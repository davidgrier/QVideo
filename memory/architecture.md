# QVideo Architecture Notes

## Package structure

The repo root `/Users/davidgrier/python/QVideo/` IS the `QVideo` Python package. The parent
directory `/Users/davidgrier/python` is on `sys.path`, so Python imports `QVideo` from the
repo root directly.

Subpackages at the repo root:
- `cameras/` — camera backends (Basler, Flir, Genicam, IDS, MV, Noise, OpenCV, Picamera, Vimbax)
- `lib/` — core abstractions (QCamera, QVideoSource, QCameraTree, chooser)
- `filters/` — image processing filters
- `dvr/` — recording subsystem
- `demos/` — demo applications (demo, filterdemo, ROIdemo)
- `devel/` — legacy/experimental backends excluded from releases (Spinnaker, Spinnaker2)
- `docs/` — Sphinx documentation (furo theme, autodoc, napoleon, intersphinx)

## GenTL producer discovery

All GenICam backends discover their `.cti` producer file via `QGenicamCamera._findProducer(*filenames)`,
which searches the `GENICAM_GENTL64_PATH` environment variable (set by all GenICam SDK installers).
`.cti` binaries are never bundled in the repo — each camera backend directory has a `.gitignore`
excluding `*.cti` and `*.cti.*`.

### Stale install warning

An old editable install once created `/Users/davidgrier/python/QVideo/QVideo/` (a subdirectory
pointing to version 2.1.0). This was deleted in a prior session. If Python appears to import
stale code, check whether that subdirectory has reappeared. The correct setup is:
- `pyproject.toml` with explicit `package-dir` mapping
- `pip install -e .` to register the editable install

## GenICam / Harvesters naming

- `device.remote_device.node_map` — Harvesters library attribute; keep snake_case as-is
- `self.nodeMap` — our own attribute on `QGenicamCamera`; camelCase per project convention

## Import collision: QGenicamCamera

`cameras/Genicam/__init__.py` re-exports the `QGenicamCamera` class directly, so:
- `import QVideo.cameras.Genicam.QGenicamCamera as m` resolves to the CLASS, not the module
- Use `sys.modules['QVideo.cameras.Genicam.QGenicamCamera']` to get the actual module object
  when `patch.object` is needed on module-level names
