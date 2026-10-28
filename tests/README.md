# tests

Run everything with `python -m pytest` (set `QT_QPA_PLATFORM=offscreen`
on a machine without a display).  No test uses real hardware.

- `conformance.py` is the contract that every camera backend must meet.
  A backend adopts it in `test_conformance_<name>.py` by defining
  `makeCamera()`, which returns a camera on a simulated device.
- `test_q<name>camera.py` tests what is specific to one camera.
- `signals.py` has `record(signal)`, which collects the arguments of Qt
  signals under every binding; `fakes.py` has stand-in sources and
  `until(condition)`.

Hardware SDKs are replaced by mocks put into `sys.modules` before the
module under test is imported.  `CONTRIBUTING.md` lists the conventions.
