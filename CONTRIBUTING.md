# Contributing to QVideo

Thank you for your interest in contributing to QVideo.  QVideo exists to
provide trouble-free access to scientific imaging with widely available
cameras, and the most valuable contribution is **support for another
camera**.  This guide covers everything you need to get started.

## What belongs in QVideo

QVideo is strictly for scientific (video) imaging: cameras, the frames
they produce, and what is done to those frames (display, filtering,
recording, analysis).  Instruments that are not cameras, such as stages,
shutters and lasers, belong in the sister project
[QInstrument](https://github.com/davidgrier/QInstrument).

If you are not sure whether an idea fits, open an issue and ask before you
write code.

## Setting up a development environment

```bash
git clone https://github.com/davidgrier/QVideo.git
cd QVideo
pip install -e ".[dev-pyqt6]"      # or dev-pyqt5
```

No build step is required: the package is used directly from the source
tree.  Run the same command again after changing the version, the
dependencies or the package list in `pyproject.toml`.

To build the documentation locally:

```bash
pip install -e ".[docs]"
sphinx-build -b html docs docs/_build/html
```

## Running the tests and the linter

```bash
python -m pytest                                  # everything
python -m pytest tests/test_qgenicamcamera.py     # one file
python -m pytest tests/test_qgenicamcamera.py::TestRead::test_frame_shape
python -m pytest --cov=. --cov-report=term-missing
ruff check .                                      # also runs in CI
```

Tests never need physical hardware: every camera backend is tested against
a mock or a simulated device.  On a machine without a display, set
`QT_QPA_PLATFORM=offscreen`.

CI runs the suite on Python 3.11 to 3.14 with PyQt6 and PyQt5 and on Linux,
macOS and Windows; it also runs `ruff check .`.  A pull request needs both
the tests and the linter to pass.

## How the code is organized

QVideo is layered: **hardware → threading → UI → application**.  Each layer
depends only on the ones below it.

| Layer | Key classes |
|-------|------------|
| Hardware | `QCamera` (abstract base), camera backends in `cameras/` |
| Threading | `QVideoSource` runs a camera in a `QThread`, emits `newFrame` |
| UI | `QCameraTree`, `QFilterRack`, `QVideoScreen` |
| Application | `QCamcorder`, `demos/` |

Each directory has a short `README.md` that says what it is for.  `lib/`
holds the base classes that you subclass (cameras, filters, readers and
writers) and the machinery that they run on; `cameras/`, `filters/`,
`dvr/` and `overlays/` hold the implementations, `demos/` the example
applications and `interactive/` the notebook interface.

`docs/architecture.rst` describes the layers in more detail, and
`CLAUDE.md` is a concise reference to the conventions of the code.

## Adding a camera backend

Read **[Writing a camera backend](docs/backends.rst)**.  It explains the
contract that a camera must satisfy and walks through a complete example.
In outline:

1. Create `cameras/<Name>/` with `_camera.py` (`Q<Name>Camera` and
   `Q<Name>Source`), `_tree.py` (`Q<Name>Tree`) and `__init__.py`.  The
   camera subclasses `QCamera` and implements `_initialize`,
   `_deinitialize` and `read`, and registers its adjustable parameters
   with `registerProperty`.  `cameras/Noise` is the reference.
2. Register it in `cameras/registry.py` (with its command-line flag),
   `QCamcorder.py`, `demos/__init__.py` and `docs/api/cameras.rst`.
3. Add `tests/test_conformance_<name>.py`: mix `CameraConformance`
   (`tests/conformance.py`) into a `TestCase` that makes your camera on a
   **simulated device**.  The suite states what the rest of QVideo relies
   on; fix the camera, not the check.
4. Add `tests/test_q<name>camera.py` for what is specific to your camera.

If the hardware SDK is an optional dependency, import it inside
`try/except (ImportError, ModuleNotFoundError)` together with every name
derived from it, and tell the user what to install when it is missing
(`QDriverError`) or when the camera is not found (`QDeviceError`).

You may not own every camera that you add support for.  Say in the pull
request what you tested on hardware and what is only tested against a mock;
we record that in `docs/compatibility.rst`.

## Adding a filter

Subclass `VideoFilter` (in `lib/QVideoFilter.py`).  A stateless filter
overrides `process(frame)`; a filter that keeps state overrides `add` and
`get`.  Add a companion `Q...Filter` widget if the filter has controls.
`filters/invert.py` is a minimal example, and `docs/extending.rst` walks
through writing filters and overlays.  Filters live in `filters/`, and
heavy ones derive from `AsyncVideoFilter` so that the display stays
responsive.

## Coding conventions

- Use **single quotes** for strings, including docstrings.
- Lines are at most **79 characters**, in Python, reStructuredText and
  Markdown prose.  `ruff check .` enforces this.
- Use **American spelling** everywhere: *color*, *normalize*, *center*,
  *gray*, *behavior*.
- Classes that derive from Qt classes use **camelCase** for attributes and
  methods (`self._isOpen`, `registerProperty`).  Slots are private:
  `_setGain`, not `setGain`.  Pure-Python classes, such as `VideoFilter`
  subclasses, use snake_case.
- Docstrings follow the NumPy style.
- Prefer small, direct solutions to elaborate ones.  Prefer OpenCV calls
  and lookup tables to NumPy expressions on whole float images; filters
  run on every frame.
- Never take a camera's lock from code above the camera, and do not call
  camera getters on the GUI thread once per frame.
- Add `# pragma: no cover` to `if __name__ == '__main__':` guards.

## Tests

- Use `unittest` with `unittest.mock`; each file has one module-level `app`
  singleton.
- Test Qt signals with `record(signal)` from `tests/signals.py`, which
  works under every Qt binding.
- Inject mock modules into `sys.modules` **before** importing the module
  under test, and patch hardware classes with `patch.object`.
- For GenICam backends, provide real Python types for `ICategory`,
  `ICommand` and the other node interfaces (not plain `MagicMock`) so that
  the `isinstance` checks in `QGenicamCamera` work.
- A test that builds a window or a thread must end like an application:
  stop the thread and close the widget before the test returns.
- Do not repeat in a subclass's test file what the base class's tests
  already check.

## Submitting changes

1. Fork the repository and create a branch from `main`.
2. Make your changes and add tests.
3. Run the full test suite and `ruff check .`.
4. Add an entry to `CHANGELOG.md` for a change that users can see.  You do
   not need to change the version number; the maintainer does that when a
   release is made.
5. Open a pull request against `main` with a clear description of what
   changed and why.  A draft pull request that does not pass yet is a good
   way to ask for help.

Do not commit media files (images, videos) outside `docs/`.

Bug reports and feature requests are welcome in
[GitHub Issues](https://github.com/davidgrier/QVideo/issues).

## License

By contributing you agree that your changes will be released under the
[GPL v3](LICENSE.md) license that covers this project.
