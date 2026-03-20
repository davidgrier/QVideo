# QGenicamCamera Notes

## Hard ImportError when dependencies absent

`QGenicamCamera.py` now re-raises as `ImportError` with a `pip install` hint when
`harvesters`/`genicam` are not installed. No stub classes needed. This is consistent with
`QGenicamTree.py` which also hard-imports from `genicam.genapi`.

## QGenicamCamera is now abstract — `producer` is a class attribute

`QGenicamCamera` has `producer: str | None = None`. Subclasses must override it.
Attempting to instantiate `QGenicamCamera` directly raises `TypeError`.
`QGenicamSource` now requires a `camera` argument (no auto-instantiation).
`QGenicamTree` now requires a `camera` argument (no auto-instantiation, `cameraID` removed).

## cameras/Vimbax/ — Allied Vision VimbaX backend

`QVimbaXCamera(QGenicamCamera)` — sets `producer` at import time by searching
`GENICAM_GENTL64_PATH` for `VimbaUSBTL.cti`, `VimbaGigETL.cti`, `VimbaCL.cti`.
`QVimbaXSource` — wraps `QVimbaXCamera`, creates one from `cameraID` when not provided.
`QVimbaXTree` — wraps `QGenicamTree`, creates `QVimbaXCamera` when not provided.
Registered in `chooser.py` under `-v` flag.

**QVimbaXTree cannot be imported in the same test session as test_qgenicamcamera.py**
because that file stubs `QVideo.cameras.Genicam.QGenicamTree` as a plain `MagicMock`
(which cannot be used as a base class). QVimbaXTree tests deferred to when
QGenicamTree gets its own test file.

## _initialize failure handling and _cleanup()

`_initialize` uses a `success` flag + `try/finally` pattern. `_cleanup()` is always
called on non-success paths. Each initialization phase has its own error handling:

- `add_file`/`update` fails → warning, harvester reset, return False
- `create` fails (any exception) → warning, harvester reset, return False
- `node_map is None` → warning, device destroyed, harvester reset, return False
- `device.start()` or `_scan_modes`/`_register_features` raises → exception propagates,
  `_cleanup()` runs via `finally` (device.stop attempted, device.destroy, harvester.reset)
- `device.is_valid() == False` → warning, device stopped+destroyed, harvester reset, return False

`_cleanup()` guards each step with try/except so it never masks the original exception.
`read()` guards against empty `payload.components` (returns `(False, None)` with warning).

**Key distinction**: `add_file`/`update`/`create`/`node_map`/`is_valid` failures return
`False` (camera is closed but usable). `device.start()` and node-tree exceptions propagate
to the caller — these are unexpected and the camera object should be discarded.

## Dynamic accessibility fixes (committed in a5261d0)

### `_make_setter` runtime mode check

Before writing a feature value, check `feature.node.get_access_mode()` at call time.
If not writable (and the feature is not in the `protected` list), log a warning and skip.
Protected features require stop/restart of acquisition — they are exempt from the early-out.

### `QGenicamTree._updateLimits()`

New method called from `_handleItemChanges` alongside `_updateEnabled`. After every UI
property change, pushes updated min/max/step/entries from live GenICam nodes into the
Parameter tree so UI constraints stay current.

## `protected` list

Tracks features whose access mode changes after `device.start()` — i.e. features that
require stopping acquisition to reconfigure.

## Import collision

`cameras/Genicam/__init__.py` re-exports `QGenicamCamera` (the class), so:
- `import QVideo.cameras.Genicam.QGenicamCamera as m` resolves to the CLASS
- `sys.modules['QVideo.cameras.Genicam.QGenicamCamera']` gives the actual module object
