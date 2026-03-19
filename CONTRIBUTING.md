# Contributing to QVideo

Thank you for your interest in contributing to QVideo.  This guide covers
everything you need to get started.

## Setting up a development environment

```bash
git clone https://github.com/davidgrier/QVideo.git
cd QVideo
pip install -e ".[dev]"
```

No build step is required — the package is used directly from the source tree.

To build the documentation locally:

```bash
pip install -e ".[docs]"
sphinx-build -b html docs docs/_build/html
```

## Running the tests

```bash
# Full suite
python -m pytest

# Single file
python -m pytest tests/test_qgenicamcamera.py

# Single test
python -m pytest tests/test_qgenicamcamera.py::TestRead::test_frame_shape

# With coverage report
python -m pytest --cov=. --cov-report=term-missing
```

Tests never require physical hardware — all camera backends are mocked.

## How the code is organised

QVideo is layered: **hardware → threading → UI → application**.  Each layer
depends only on the ones below it.

| Layer | Key classes |
|-------|------------|
| Hardware | `QCamera` (abstract base), camera backends in `cameras/` |
| Threading | `QVideoSource` — wraps a camera in a `QThread`, emits `newFrame` |
| UI | `QCameraTree`, `QFilterBank`, `QVideoScreen` |
| Application | `QCamcorder`, `demos/` |

`cameras/Noise` is the reference backend — read it before writing a new one.

## Adding a camera backend

1. Create `cameras/<Name>/Q<Name>Camera.py` — subclass `QCamera` and
   implement `_initialize`, `_deinitialize`, and `read`.  Call
   `registerProperty` / `registerMethod` inside `_initialize` for every
   adjustable parameter.
2. Create `cameras/<Name>/Q<Name>Source.py` — subclass `QVideoSource`; wrap
   the camera in `__init__`.
3. Create `cameras/<Name>/__init__.py` — export both classes and set `__all__`.
4. Add a test file `tests/test_q<name>camera.py`.  Hardware dependencies must
   be mocked via `sys.modules` before importing the module under test; see the
   existing backend tests for the pattern.

If the hardware SDK is an optional dependency, wrap the import in
`try/except (ImportError, ModuleNotFoundError)` and provide stub names for
any module-level symbols used in class bodies or function signatures.

## Adding a filter

Subclass `VideoFilter` (in `lib/VideoFilter.py`) and implement `__call__`.
See `filters/QBlurFilter.py` for a minimal example.  Filters live in
`filters/` and are stateless or carry only lightweight state.

## Coding conventions

- **Qt classes use camelCase** for all instance attributes and private
  names: `self._isOpen`, `self.nodeMap`, `self._colorCapable`.
- **Pure-Python classes use snake_case** (e.g. `VideoFilter` subclasses).
- Docstrings follow NumPy style.
- Add `# pragma: no cover` to `if __name__ == '__main__':` guards.
- Soft dependencies belong entirely inside the `try` block — never reference
  imported names after the `except` clause.

## Tests

- Use `unittest` with `unittest.mock`; one module-level `app` singleton per
  file.
- Inject mock modules into `sys.modules` **before** importing the module
  under test.
- For GenICam backends, provide real Python types for `ICategory`, `ICommand`,
  etc. (not plain `MagicMock`) so `isinstance` checks in `QGenicamCamera` work.
- Use `QtTest.QSignalSpy` to test Qt signals.

## Submitting changes

1. Fork the repository and create a branch from `main`.
2. Make your changes and add tests.
3. Run the full test suite — all tests must pass.
4. Open a pull request against `main` with a clear description of what changed
   and why.

Bug reports and feature requests are welcome via
[GitHub Issues](https://github.com/davidgrier/QVideo/issues).

## Licence

By contributing you agree that your changes will be released under the
[GPL v3](LICENSE.md) licence that covers this project.
