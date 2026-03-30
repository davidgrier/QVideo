---
name: Feature 2 — composite overlay recording
description: Status of composite recording feature (QVideoScreen.composite + CompositeDemo)
type: project
---

## Status: COMPLETE (2026-03-29)

### What was implemented

- `QVideoScreen.newFrame` signal: emits filtered frame (or composite RGBA
  array) after each displayed frame.
- `QVideoScreen.fps` property: returns `_framerate` when throttling is active,
  else delegates to `source.fps` — the effective display rate.
- `QVideoScreen.composite` bool property: when `True`, `_renderComposite()`
  captures the widget via `QWidget.grab()` and emits the RGBA result via
  `newFrame` instead of the filtered frame.
- `QVideoScreen._renderComposite()`: uses `self.grab()` (not
  `QGraphicsScene.render()`) to avoid painter conflicts with pyqtgraph's
  internal rendering.
- `QDVRWidget` unchanged: records from any object with `.newFrame` signal and
  `.fps` — composite mode is transparent to the DVR.
- `CompositeDemo` (`demos/compositedemo.py`): subclasses `QCamcorder`, adds
  `QTrackpyWidget` panel and a "Composite" `QCheckBox`.  When checked,
  `screen.composite = True` and `dvr.source = screen`; when unchecked,
  reverts to raw frames.

### Design rationale

`QVideoScreen` acts as a frame source via duck typing: anything with `.newFrame`
and `.fps` can be a DVR source.  The application (`CompositeDemo`) decides
which signal to record — the DVR itself has no concept of composite mode.

### Tests

New test classes in `tests/test_qvideoscreen.py`:
- `TestFps`, `TestNewFrame`, `TestComposite`
