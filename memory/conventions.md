# QVideo Coding Conventions

## Naming convention: camelCase for Qt class instance attributes

All instance attributes on Qt subclasses use camelCase (matching PyQt/Qt C++ style).

### Renamed attributes (completed, committed in 5fcc44e)

| Old name | New name | Location |
|---|---|---|
| `_isopen` | `_isOpen` | `lib/QCamera.py` |
| `node_map` | `nodeMap` | `cameras/Genicam/QGenicamCamera.py` (our attr only) |
| `_ignore_sync` | `_ignoreSync` | `lib/QCameraTree.py` |
| `_color_capable` | `_colorCapable` | `cameras/Spinnaker/`, `cameras/Spinnaker2/` |
| `_low_spinbox` | `_lowSpinbox` | `filters/QEdgeFilter.py` |
| `_high_spinbox` | `_highSpinbox` | `filters/QEdgeFilter.py` |
| `_order_buttons` | `_orderButtons` | `filters/QSampleHold.py` |
| `_reset_button` | `_resetButton` | `filters/QSampleHold.py` |

Note: `device.remote_device.node_map` (Harvesters library attribute) keeps snake_case.

## Test conventions

- Tests use `unittest` with `unittest.mock`; each file has a module-level `app` singleton.
- Qt signals are tested with `QtTest.QSignalSpy`.
- Hardware is always mocked — never rely on physical devices in tests.
- For cameras with optional dependencies, inject mock modules into `sys.modules` before import.
- `# pragma: no cover` on all `if __name__ == '__main__':` guards.
- Docstrings use NumPy style.

## Soft dependencies

Hardware-specific packages are soft dependencies. Import pattern:

```python
try:
    from some_hardware_lib import SomeClass
    # ALL names derived from the import go inside the try block
except (ImportError, ModuleNotFoundError):
    SomeClass = None
    # Stub any names used in class body or type annotations
```

Any module-level names derived from optional imports must be inside the `try` block — not after it.
