# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Changed

- **The type check of `lib/` is clean, and CI enforces it.**  `pyright`
  reports no error in the environment that CI uses (PyQt6 alone), where it
  reported 106, and the `Types` job now fails the workflow on one (pyright
  is pinned to 1.1.414).  The reports were mostly a project setting (`extraPaths`, so that `QVideo.*`
  resolves in CI) and annotations that said less than the code knows:
  `QReferenceFilter.videoFilter` is a `ReferenceFilter`, the pending frame
  of `QVideoScreen` is a frame and its information, overlays are graphics
  items, and `lib.__all__` is a list.  Qt enums are spelled in full
  (`Qt.ConnectionType.DirectConnection`), which works under PyQt5 too.
  `ReferenceFilter.add` names its argument `data`, like `VideoFilter.add`.
  The rest are casts of OpenCV and Qt results and a few
  `# pyright: ignore[rule]` where the stubs are too narrow.

---

## [4.19.0] — 2026-11-08

### Added

- **`camera.frames(n)`, `camera.stack(n)` and `camera.save()` in the
  notebook.**  `frames` reads `n` filtered frames as a list and `stack` joins
  them in one array (`(n, H, W)`); `save(filename=None, image=None)` writes a
  new frame, or the image that it is given, and returns the path (a
  timestamped `camera_*.png` in the current directory by default; a deep
  camera goes to a 16 bit PNG or TIFF stretched by its levels).  It raises
  `ValueError` or `OSError` where the Qt saver reports them in the status
  bar.
- **`camera.show()` and a levels control for the notebook live view.**
  `camera.show(image=None, contrast='auto')` displays one frame as a PNG
  (auto contrast, `'camera'`, `'full'` or `(black, white)` for a deep frame).
  `camera.live_view()` of a camera of more than 8 bits adds a **Levels**
  drop-down under the picture (camera range, auto contrast, full 16 bits);
  it used to hand the `uint16` frame to the JPEG encoder.  The percentile
  rule is `imageops.AutoLevels`, which `QVideoScreen.autoLevels` now uses
  too, so that the window and the notebook scale a frame alike.
- **`camera.record(filename, n=None, seconds=None)` in the notebook.**  It
  records filtered frames to a video file in any format of the DVR panel
  (`.mkv`, `.avi`, `.mp4`, `.h5`) and returns the path when the recording is
  complete, so a cell can run an experiment without a window.  It stops at
  `n` frames or after `seconds`, whichever comes first, declares the frame
  rate of the camera (or `fps=`), refuses to replace a file unless
  `overwrite=True`, closes the file on an interrupt, and raises
  `RuntimeError` with the reason if the writer stops early.

---

## [4.18.0] — 2026-11-07

### Added

- **Choose the camera by name, or from a list.** The `cameraID` of the
  command line may be text: `python -m QVideo -c C920` opens the OpenCV
  camera whose name contains `C920`.  With a flag but no `cameraID`, or
  with text that fits several cameras, `launch()` shows a list and asks
  which to open (cancelling ends the program); an index never asks.  A
  backend that lists no device names behaves as before.
  Under PyQt5, which has no `QMediaDevices`, the cameras are named by
  `QCameraInfo` (they were `Camera 0`, `Camera 1`).

- **Frames of more than 8 bits keep their counts through the filters and the
  screen.**  These filters are now `deep`: they receive a `uint16` frame
  and keep its scale (`VideoFilter.levels` is the black and white that the
  pipeline sets, `VideoFilter.bounds(frame)` returns them): `DarkFrameFilter`,
  `FlatFieldFilter` (the reference remembers its type, so an 8 bit reference
  never corrects a deep frame), `InvertFilter` (black + white - pixel),
  `UnsharpFilter`, `DoGFilter`, `MoMean`, `Median`, `MoMedian`, `Normalize`,
  `SampleHold` and, for the methods that OpenCV runs on `uint16` frames,
  `SmoothingFilter` (not the median) and `ThresholdFilter` (global, at the
  same fraction of the range).  Every other filter still gets the 8 bit
  copy.  A median background starts again when the type of the frames
  changes.  `prepare(filter, frame, levels)` is the one rule, used by the
  pipeline, by `QFilterRack.__call__(frame, levels)` and by the notebook
  `Camera()`, which scaled nothing before.
- **`QImageSaver` and `imageops.save_image` save any image.**
  `save_image(image, filename, levels=None)` writes a gray, RGB or RGBA
  array of `uint8` (or `uint16`, as `QSnapshot` did) and raises
  `ValueError` or `OSError` when it cannot.  `QImageSaver.save(image,
  filename=None, ask=False)` adds a timestamped name that never overwrites a
  file, an optional file dialog and a `message(str)` signal for the status
  bar, and returns the path.  An application passes the image in (the
  screen, the pattern of a modulator), so it is no longer tied to the
  frames that `QSnapshot` caches.  `QSnapshot` now uses it, and `QCamcorder`
  shows "Saved ..." in its status bar after a snapshot.
- **An application remembers where it saved.**  `QSnapshot` starts in the
  directory of the last snapshot or screenshot, and the DVR panel of
  `QCamcorder` offers the file of the last recording or playback (so the
  format too).  The memory is the platform's own (`QSettings`: a property
  list on macOS, a file on Linux, the registry on Windows), is written when a
  file is actually written or opened, and ignores a directory that has gone.
  Only an application with a name of its own remembers anything: `launch()`
  names it from its title, an embedding program calls
  `QCoreApplication.setApplicationName`, and a bare script (named `Python`
  by Qt) gets nothing.  `QImageSaver(key=...)` and `QDVRWidget(key=...)`
  opt in; without a key they behave as before.
- **A screenshot of what the screen shows.**  `QVideoScreen.screenshot()`
  (it was the private `_renderComposite`) renders the video with its filters,
  color map and overlays when it is called.  `QSnapshot(parent, screen=...)`
  adds `screenshot()` and `screenshotAs()`, on `Ctrl+Shift+P` (silent,
  timestamped) and `Ctrl+Shift+Alt+P` (file dialog), which `QCamcorder`
  turns on beside the data snapshot.  Without a `screen` nothing changes.
- **A deep frame is saved and recorded honestly.**  `QSnapshot` saves a gray
  `uint16` frame to PNG or TIFF with 16 bits, stretched so that the levels
  of the camera run from 0 to 65535 (it refused such a frame before), and
  anything else with 8 bits; both `.mp4` writers hold 8 bits and now scale
  the frames between their levels, and say so in the log (the OpenCV writer
  refused them).  `imageops.stretch16` does the stretching.
- **`QVideoScreen.autoLevels`** shows the percentiles of the frame (for
  example `(1, 99)`) as black and white, estimated from a subsample every
  five frames and smoothed, so a dim 12 bit image fills the screen without
  a filter and without changing the data.  `QCamcorder` shows a choice of
  levels (the camera's, auto contrast, the full 16 bits) when a frame brings
  levels.

- **A Performance page and a script that makes its tables.**
  `benchmarks/benchmark.py` measures the frames per second that reach the
  GUI thread from a synthetic camera, with the delay (median and 99th
  percentile), CPU and dropped frames; the time that each filter needs for
  a frame; and the speed and compression of each file writer.  `camera -c`
  (or any camera flag) measures a camera that is attached, `--exposure`
  turns off its automatic exposure and sets the time, and `--csv` saves
  the tables.  `docs/performance.rst` has the results for one machine
  and what is not measured.
- **A USB3 Vision camera under Viva gives a hardware timestamp.**  Only a
  GigE Vision camera can be calibrated to host time, so every frame of a
  USB camera had `hardwareTimestamp = None` and a recording held NaN in
  `hardware_timestamp`.  The frame now carries the clock of the camera (its
  ticks, which are nanoseconds: 999.8 million a second against the host
  clock on a Blackfly S), good for the time between frames and not for the
  time of day.  A GigE camera that fails to calibrate is reported with a
  warning.

- **A camera that is lost fails once and then answers quietly.**  When a
  USB or network camera is unplugged, `QCamera._deviceLost(reason)` closes
  it, logs one error and emits the new `lost(str)` signal (passed on by
  `QVideoSource`).  The tree disables its controls, `QCamcorder` shows a
  dialog (a headline, what to do, and the technical reason behind a
  "Show Details" button) and a short message in the status bar, and the last
  frame stays on the screen; filters, overlays and playback carry on.  A closed camera
  answers `saferead()` with `(False, None)`, `get()` with `None`, and
  refuses `set()` and `execute()` with a warning.  The capture loop waits
  50 ms between asks of a closed camera instead of reading as fast as it
  can: with an unplugged Blackfly S under Viva it did a million reads a
  second and used a whole core, without a word in the log.  `QVivaCamera`
  reports the loss when its stream ends, and `QOpenCVCamera` when a live
  camera (a webcam or a network stream, not a video file) sends no frame for
  `lossTimeout` seconds (2; `None` turns it off).  Nothing reconnects;
  restart the program.  A camera counts as open while `_initialize` runs, so a
  backend can read and write its device there.

### Changed

- **`QOpenCVCamera` opens a camera by what stays with it.**  `cameraID` may
  be the unique identifier that the system gives the device, or a part of
  its name (`'C920'`) that only one camera has, as well as an index; an
  unknown or ambiguous name raises `QDeviceError` with the list of cameras.
  `QOpenCVDevices.devices()` lists each camera with its index, name and id
  (`CameraDevice`), `QOpenCVDevices.find()` looks one up, and an open camera
  has `modelName` and `deviceID`.  The command line still takes an index.

- **`QCamcorder` shows a dialog when a recording stops by itself**: a
  headline, and the reason (for example that the writer fell behind the
  camera, and what to try), in addition to the status bar.  The dialog does
  not block the video.
- **Recording 16-bit gray video to `.avi` is 3.5 times faster.**  FFV1 is
  slow on 16-bit pixels (55 frames a second of 1280 x 1024, against 460 for
  8-bit), so the PyAV writer now uses FFVHuff for them in an `.avi` file:
  also lossless, 194 frames a second, files 40% larger.  A 16-bit `.mkv`
  file stays on FFV1 (Matroska has no FFVHuff), and the dialog that says a
  recording fell behind now suggests `.avi` or `.h5` for it.
- **The Viva tree starts with manual exposure and gain**, as the Flir tree
  does: `ExposureAuto` and `GainAuto` are `Off`.  An automatic exposure
  changes under a measurement, and by lengthening the exposure it lowers
  the frame rate (66 frames a second where the camera can do 437).  The
  exposure that the automatic mode last chose is kept, so lower it to
  reach the full rate.
- **The YOLO and trackpy workers log the traceback of the first failure**
  of a detection, as a warning; the failures that follow, one for each
  frame, are logged at debug level, and a failure after a success is
  reported again.  A bug in the detection no longer looks like an ordinary
  failure.
- **Continuous integration** runs `pyright` on `lib/` in a job that does not
  fail the workflow, and checks a coverage floor of 95% (the suite measures
  96%) in one test job.  `pyright` is configured in `pyproject.toml`; run
  `pyright` to see its report.

### Fixed

- **The chooser named the wrong OpenCV camera.**  OpenCV gives the cameras
  no names and numbers them as its backend does, and the list of names came
  from Qt, which lists them in the order in which the system found them.  On
  a Mac with a USB webcam and the built-in camera Qt put the built-in camera
  first, OpenCV opened the webcam as 0 (it sorts the cameras by their
  unique ids), and "HD Pro Webcam C920" in the chooser opened the FaceTime
  camera.  The names now follow OpenCV's index: sorted by id on macOS, the
  `N` of `/dev/videoN` on Linux (`cameras()` numbered by position before,
  which is wrong when `video1` is a metadata node).  Windows is not checked.
- **The docstring of `launch()` had a stray line** (`XX`) in the middle of a
  sentence, which Sphinx reported as a warning and which was on the page
  of the API since 4.17.0.
- **The frame rate control of `-g` (Viva) was gray until something enabled
  it.**  A camera makes `AcquisitionFrameRate` read-only while
  `AcquisitionFrameRateEnable` is off, which is how it leaves the factory,
  and the Viva tree shows no control for the enable.  The Flir, Basler and
  IDS trees switch it on when they start; the Viva tree does now.
- **Importing `QVideo.overlays.yolo` no longer slows OpenCV.**  `ultralytics`
  calls `cv2.setNumThreads(0)` when it is imported, which left the whole
  program with one OpenCV thread and made an ONNX model run four times as
  long (98 ms a frame, against 27 ms).  The module imported it at the top;
  it is imported now when a `.pt` model is first loaded, and the number of
  threads is put back after the import.  The OpenCV backend has now been
  tested on a real export (`yolo11n`): it finds the same objects as
  `ultralytics`.
- **Edge cases that the type checker found.**  A `QFilterPipeline` with no
  source (a rack that has none yet) has a frame rate of 0 and an empty
  shape instead of raising `AttributeError`, and ignores a rack that has
  gone.  `QFrameRelay` ignores a wake-up that has no frame.  A reader that
  reports success with no frame ends the iteration, and indexing it raises
  `IndexError`.  A camera in a process of its own (`QRemoteCamera`) fails
  the read of a frame that is announced after it was closed, and its worker
  says that it has no ring yet, instead of failing on `None`.

---

## [4.17.0] — 2026-11-06

### Added

- **A deep camera's levels travel with its frames.**
  `FrameInfo.levels` is the black and white of the pixels of a camera
  whose counts have fewer bits than their type (`(0, 4095)` for 12 bit
  counts in `uint16`), `None` otherwise.  `QCamera.levels` is where a
  camera sets it; `QGenicamCamera` and `QVivaCamera` derive it from
  `PixelFormat` when it can change (at opening and in `set`), not for
  each frame, so a change of format reaches the display on the next frame.
  `QRemoteCamera` carries it across the process boundary.  The screen
  shows each frame between its levels (`screen.levels = ...` still wins;
  `None` hands the decision back to the frames), and `QHDF5Writer` leaves
  the levels in the file as an attribute that `QHDF5Reader` hands on.
- **The filter pipeline scales a deep frame for the filters that cannot
  take one.**  Before a filter that is not `deep` (`VideoFilter.deep`,
  `False` by default) a `uint16` frame becomes `uint8` between its levels
  (`imageops.to8bit`), and the frames after it have no levels.  `ROIFilter`
  is `deep`: a crop keeps the counts.  Four filters raised on `uint16`
  frames and others gave wrong scales, so each filter has to be tried on
  counts before it is marked `deep`.
- **`QVideoScreen.levels`**: the values that the display shows as black and
  as white.  The default, `None`, maps the whole range of the type of the
  frame, so a 12 bit frame in `uint16` looked 16 times too dark; set
  `screen.levels = (0, 4095)` to show it.  An explicit range makes
  pyqtgraph rescale each frame, which cost about 7 ms for a `uint16` frame
  of 1280 by 1024 (2 ms without).
- **`lib.dnn`: a helper that runs a neural network with OpenCV.**
  `DNN(path, size=...)` loads an ONNX file (or anything else that
  `cv2.dnn.readNet` reads), turns a frame into the input of the network
  and `forward()` returns the outputs; `letterbox()` and `prepare()` do the
  usual preprocessing.  It has no Qt in it, so a filter, an overlay worker
  or a script can use it, and `engine`, `backend` and `target` pass on the
  choice of the DNN engine.  The standard `opencv-python` wheels run on the
  CPU only.
- **`QYoloOverlay` runs an ONNX model with OpenCV, with no `torch`.**
  `QYoloWidget` takes `backend` (`'auto'`, `'ultralytics'` or `'opencv'`),
  `imgsz` and `names`; `'auto'` uses OpenCV for a file that ends in
  `.onnx` and `ultralytics` for anything else, so existing code is
  unchanged.  `yolo.decode()` reads the output of an Ultralytics YOLOv8 or
  later detection export, `(1, 4 + classes, N)`, and applies non-maximum
  suppression.  The documentation says how to export a model and warns that
  Ultralytics licenses its weights, and files exported from them, under the
  AGPL-3.0; QVideo ships no model.  **Tested on synthetic outputs and a
  network written by hand, not yet on an export from Ultralytics.**
- **The YOLO overlay labels each box with its class**, on by default, in a
  tab that keeps its size on the screen as the video is zoomed.  The Labels
  check box, `labels=False` and `--no-labels` turn it off.
- **`YoloDemo` takes the model from the command line:** `--model`,
  `--backend`, `--imgsz`, `--names` and `--no-labels`.
- **`--version` and `--log-level` for every demo and `QCamcorder`.**
  `--version` prints the version and ends; `--log-level` (`DEBUG` to
  `CRITICAL`, in either case) sets the level of the `QVideo` loggers and
  adds a handler that writes to the standard error stream, so that `INFO`
  and `DEBUG` messages appear.  Without the option, logging is as it was.
- **`--help` says what the program is.**  The description is the first
  paragraph of the docstring of the widget, the camera options are in a
  group of their own, and examples and the address of the documentation end
  the message.  `lib._launch.argumentParser(widget, examples)` builds the
  parser for a program of your own.
- **`QOpenCVWriter` and `QOpenCVReader` handle 16-bit gray video.**  The
  writer uses FFV1 with a depth of 16 bits (OpenCV 4.7 or newer, with
  FFmpeg) and tries no lossy codec for such frames; the reader returns
  `uint16` frames for such files.  `.mp4` cannot hold them.
- **Documentation:** a table of the camera backends with their flags and
  what each needs; the DVR file formats and what a recorder needs from its
  source; recording the composite of the screen and its overlays.  A
  second Blackfly S (BFS-U3-04S2M-CS) delivered 500 frames a second at
  720 by 540 through Viva.

### Changed

- **GenICam cameras start with gamma 1 and off.**  The FLIR and Basler
  trees enabled gamma without setting it, and the cameras power up with
  their own value (0.8 on FLIR).  `QGenicamTree` and `QVivaTree` now apply
  `Gamma=1.0` and `GammaEnable=False`, the vendor trees build on those
  defaults, and `GammaEnable` is one of the standard controls, so that the
  setting is visible.  A program that wants a gamma sets it, or restores
  the settings of its own.  VimbaX has no tree defaults and is unchanged.
- **`interactive.live_view` reads and encodes each frame in a worker
  thread**, so that the kernel of a notebook no longer waits for the
  camera.
- **Release note:** 4.16.0 was bumped in `pyproject.toml` but never tagged
  or published; its changes are in this release.

### Fixed

- **`QGenicamCamera` imported with a `TypeError` on Python before 3.14.**
  The method `set()` shadows the builtin in the class body, so the
  annotation `set[str]` raised; it is quoted now.

---

## [4.15.1] — 2026-11-04

### Changed

- **The camera tree has no "Parameter / Value" header.**  The labels said
  nothing that the rows do not.  `QCameraTree(source, showHeader=True)`
  brings it back.

### Fixed

- **A Wayland warning at start-up** ("Wayland does not support
  QWindow::requestActivate()").  The splash screen asked to be activated,
  which macOS needs and Wayland cannot do; the request is now made only
  where it works.

---

## [4.15.0] — 2026-11-04

A pass for structure: classes and names that exist because of the order in
which the code was written.  Three changes are breaking
(`QFilterRackWidget`, `QVideoWriter.blank` and `QVideoFilter.filter`); the
platform has few users yet, and there is no deprecation shim for them.

### Removed

- **`QFilterRackWidget`.**  It was the base class of `QFilterRack`, and
  `QFilterRack` added only the pipeline that it owns.  `QFilterRack` is now
  one class, with the same constructor, in `QVideo.lib.QFilterRack`.  Code
  that built a `QFilterRackWidget` to filter recorded frames builds a
  `QFilterRack` and calls it; the rack's pipeline then waits for a source.
- **`QGenicamCamera.isReadWrite`.**  Nothing called it since the trees
  began to ask `states()`.
- **`QVideoWriter.blank`**, which made a writer write black frames.
  Nothing in QVideo set it.

### Changed

- **`QVideoFilter.filter` is now `QVideoFilter.videoFilter`** (breaking).
  The attribute is the `VideoFilter` that a widget wraps; the old name
  shadowed a builtin.  A filter widget that subclasses `QVideoFilter` reads
  `self.videoFilter`.
- **The chooser.**  `Camera()` tries the backends in the order of the table
  `BACKENDS`; there is no separate `_DISCOVERY_ORDER` to keep in step.  A
  camera class answers `precheck()` and `deviceNames()` (new hooks of
  `QCamera`, which accept everything and list nothing by default) instead
  of the chooser asking by name; the OpenCV camera lists its devices.
  `open_first` and `working` share one loop.  `ensure_qapp` is in `lib`.
- **`QGenicamCamera` classifies a node once.**  Seven methods each walked
  the same chain of node types; `_nodeKind` now does, and `_limits` says
  what bounds a node, for the properties, the plain-data tree and the
  live snapshots.  Nothing visible changes.
- The class-level tables and lists of the backends, filters and writers
  (default controls and settings, codec maps, alias nodes) are tuples or
  annotated `ClassVar`; `QGenicamTree.STANDARD_CONTROLS` is a tuple, and
  `controls` takes any sequence of names.
- **CI checks more.**  `ruff` also enforces `SIM` (without `SIM905`),
  `PERF`, `PIE`, `RUF012`, `PLW2901` and `UP037` for the package.

### Documentation

- The README lists the 23 filters that a rack offers, by category; it
  still named `QBlurFilter` and `QYOLOFilter`, which no longer exist.
- The API page of the chooser documents `BACKENDS`, `discover`,
  `create_camera`, `open_first`, `working` and `uses_worker`, which its text
  already linked to.
- The guide to writing a backend describes `precheck()` and
  `deviceNames()`.  The page of camera backends says that the
  `Q<Name>Source` classes are deprecated.

---

## [4.14.0] — 2026-11-04

A pass for duplication: code and concepts that said the same thing twice.

### Deprecated

- **The `Q<Name>Source` classes of the backends** (`QNoiseSource`,
  `QOpenCVSource`, `QPicameraSource`, `QIMXSource`, `QGenicamSource`,
  `QBaslerSource`, `QFlirSource`, `QIDSSource`, `QMVSource`,
  `QVimbaXSource`, `QVivaSource`).  Each only wrapped its camera in a
  `QVideoSource`; write `QVideoSource(QNoiseCamera())` instead.  The old
  names still work and warn; they will be removed in the next major
  release.

### Changed

- **Exported filter code.**  A test now runs the code that every
  filter exports and compares it with what the filter does, on gray and
  color frames, instead of looking for strings in it.  `FilterCode` takes
  any collection of import lines and `GRAY_LINES` is the conversion to
  gray that six filters repeated.  The exported code of the horizontal
  and vertical Sobel filters no longer imports NumPy, which it did not
  use.
- **A backend is a camera and a tree.**  The vendor trees of Basler, FLIR,
  IDS, MV and VimbaX share their code in `QGenicamTree`: a subclass names
  its camera class, its default controls and its default settings.  The
  worker process of `QRemoteCamera` is in the package `QVideo.lib.remote`
  with its proxy and protocol (`from QVideo.lib import QRemoteCamera` is
  unchanged).  `chooser.camera_class` and `chooser.tree_class` return the
  classes of a backend.

---

## [4.13.0] — 2026-11-03

This release opens the Harvesters backends in a process of their own, makes
the Viva backend the preferred interface to GenICam cameras, announces a
change of shape in one place, and fixes the bugs that a review of the core
of the code found.

### Added

- **`QCameraOpener`** (`QVideo.lib`) opens the camera that the command line
  names in a thread of its own, so that a program can build the rest of its
  interface meanwhile.  `launch()` uses it, and so can a program that has
  more to start than a camera (QHOT opens its SLM and makes its hologram
  engine while the camera opens).  It was a private class of `launch()`
  and a copy in QHOT.
- **`QCamera.modelName`** is the camelCase name of `model_name`, which
  stays.
- **`QGenicamCamera.precheck()`** raises in the program, before a worker
  starts, what opening the camera would raise for want of a producer.  The
  chooser calls it, so `Camera()` and the camera chooser no longer start a
  process for every Harvesters backend that has no producer.
- **`QVivaCamera.updateAccess()`** gives a setter to the features that the
  camera lets us write now and takes it from the others; `QVivaTree` calls
  it after every change.

### Changed

- **`QCamera.set()` announces a change of shape, in one place.**  It reads
  `shape` before and after the setter of a property in `shapeProperties`
  (by default `width` and `height`; OpenCV adds `resolution`) and emits
  `shapeChanged`, once, if the shape is different.  The backends no longer
  emit it from their setters (Noise, OpenCV) or from a `set()` override
  (Genicam, Viva); a proxy that is told the shape by its worker lists none.
  A setting that leaves the size as it was announces nothing, `resolution`
  in OpenCV announces once and not once for the width and once for the
  height, and the conformance suite checks it for every backend.  Picamera
  still announces a change of color itself, because the size is the same.
- **The Viva backend (`-g`) is the preferred interface to GenICam
  cameras.**  The compatibility page says when to use it, shows the
  measurements next to those of the Harvesters backends, and the README, the
  quickstart, the help text of `-g` and the docstrings point to it.  The
  Harvesters backends remain for cameras that need a vendor's producer; they
  need the `.cti` file and hold the interpreter lock, so QVideo runs them in
  a process of their own (next entry).
- **The Harvesters backends open in a process of their own, and the `-r`
  flag is gone.**  Basler, Flir, IDS, MV and VimbaX read frames through a
  binding that holds the interpreter lock and freezes the other threads of
  the program.  On macOS and Linux the chooser now opens them in a worker
  process (`QRemoteCamera`) whatever the program: every application that
  uses `launch`, `Camera()` and `available_cameras()`.  Each entry of
  `BACKENDS` has a `worker` field, `uses_worker(key)` says whether a backend
  uses it, and the `remote` parameter of `create_camera` and `open_first` is
  gone.  On Windows, where there is no worker yet, these backends still open
  in the program.  Creating the class yourself (`QFlirCamera()`) keeps the
  camera in the program, and `QRemoteCamera` itself is unchanged.  A `-r`
  left on a command line is ignored, like any argument that no part of the
  program claims, so `python QCamcorder.py -fr` still selects the Flir.
- **`pip install QVideo[genicam]` installs viva-genicam** with harvesters,
  on the platforms for which viva-genicam publishes wheels (macOS on Apple
  silicon, Linux on x86-64, 64-bit Windows); `QVideo[viva]` installs it
  alone.
- **`QVivaCamera` has run on hardware.**  On a FLIR Blackfly S (USB3
  Vision), the camera opens in half a second, delivers 170 frames a
  second to a program, holds no interpreter lock, and passes the
  holographic-trapping gate of QHOT in the same process, without a worker:
  event-loop median 4.9 ms, 99th percentile 8.7 ms, 9.8 holograms a second
  (the remote Genicam camera: 4.6 ms, 8.2 ms, 9.9 holograms a second).
- **`QVideoSource` keeps its lock to itself.**  `mutex` and `waitcondition`
  are now `_mutex` and `_waitCondition`, and `source` is read-only.  Nothing
  outside the tests used them.
- **A worker that cannot open its camera for a reason it explains** (a
  `QCameraError`) no longer prints a traceback on the terminal of the
  program; the proxy reports the message.  Any other failure keeps its
  traceback.
- **`QCamera.shape`** is `QSize(0, 0)` when the width or the height cannot
  be read at the moment (a GenICam getter answers `None`), and no longer
  raises `TypeError`.
- **The fit of a window to the video** counts the title bar and the borders
  against the available area of the screen.

### Fixed

- **The examples import `qtpy` or QVideo before `pyqtgraph`.**  With both
  PyQt5 and PyQt6 installed, `pyqtgraph` imported first chooses its own
  binding and `QT_API` is ignored.  The README and the quickstart now show
  the safe order, `QHistogramWidget` imports `qtpy` like the other modules,
  and a test (`tests/test_import_order.py`) keeps the order.
- **The tree of a camera no longer reads the whole camera after a change.**
  It re-read every setting and set each in the tree, which warns about a
  property that it does not show: a tree of 15 controls on a camera of 2000
  properties (the Viva tree on a Blackfly S) made 2000 reads and 2000
  warnings for each change.  It now reads back what it shows, and skips a
  property that cannot be read at the moment.
- **A control that the camera locks follows the camera.**  The exposure time
  of the Viva tree stayed disabled for good if the camera started with the
  exposure automatic, and stayed enabled when it became so.
- **A NaN or an infinite value no longer stops a tree from being built**
  (`ValueError` or `OverflowError` in the step of a spin box), and the tree
  no longer hides the debug messages of its module.
- **A filter rack with a filter that has no result yet** (a sample-and-hold
  before its first sample) ends the frame, as the pipeline does, and no
  longer hands `None` to the next filter.
- **A worker that goes while a frame is announced** is a failed read, and
  no longer ends the capture thread with an exception.
- **A video file that stores no frame rate** made OpenCV answer 0 and PyAV
  `None`, and the reader and the widget divided by it.  The readers answer
  30, as the HDF5 reader does.  The extension of a file is compared without
  regard to case, so `IMG_0001.MP4` is a video.
- **A window taller than the screen** is no longer shrunk by the window
  manager, which was the cause of a resize loop in QHOT; the video then
  fills the window without bars.  Setting a colormap that cannot be made
  no longer leaves the old one in use under the new name.
- **A notebook that displays an unopened `Camera()` no longer opens it.**
  The proxy forwards public names only; IPython looks for `_repr_html_` and
  the like.
- **The probe of an OpenCV camera releases the capture device** on every
  path, including when probing raises.
- **The documentation** lists `-g` where it listed `-r` or nothing, and
  describes `target`, `framenumber` and `blank` of `QVideoWriter` as they
  are.

---

## [4.12.0] — 2026-11-02

### Added

- **`QVivaCamera`: GenICam cameras through viva-genicam (experimental).**
  `viva-genicam <https://github.com/VitalyVorobyev/viva-genicam>`_ is a
  GenICam stack in Rust that speaks USB3 Vision and GigE Vision itself,
  so it needs no GenTL producer and no vendor SDK, and, unlike the
  ``genicam`` binding of Harvesters, it releases the interpreter lock
  while a thread waits for a frame.  `QVivaCamera`, `QVivaSource` and
  `QVivaTree` are selected with `-g` and installed with
  `pip install QVideo[viva]`.  The camera passes the conformance suite on
  the fake USB3 Vision camera of the package; it has not yet run on
  hardware.
- **`QRemoteCamera`: a camera in a process of its own.**  A worker process
  opens the camera and reads its frames into a ring of shared memory; the
  proxy in the program is a `QCamera`, so sources, trees and widgets work
  with it unchanged.  Any backend can run this way: `QRemoteCamera('opencv')`,
  or `-r` on the command line of any program that uses `launch` or the
  chooser (`python QCamcorder.py -cr`).  A vendor library that holds the
  interpreter lock, such as the `genicam` binding under harvesters, can then
  freeze only the worker.  It is available on macOS and Linux; on Windows it
  raises `QCameraError`.

### Changed

- **`QGenicamTree` builds from plain data.**  `QGenicamCamera.nodeTree()`
  describes the node map as numbers, strings, lists and dicts, and the tree
  no longer touches genicam objects, so it works with a camera in a process
  of its own (`python QCamcorder.py -fr`).  `QRemoteCamera` forwards
  `nodeTree`, `hasNode` and `states`.
- **A tree does not wait for a remote camera.**  The worker of a
  `QRemoteCamera` reads the nodes that the tree watches (`watch()`), a few
  at a time between frames, and pushes their states; the five polls a second
  of `QGenicamTree` read the latest push (`states(names, cached=True)`)
  instead of making the interface wait for the frame in progress.  A setting
  discards the pushed states, so what follows it is read afresh.
- **A remote camera announces every change of shape.**  The worker sends a
  `shape` event ahead of the first frame of a new shape, whoever changed it:
  a request, or the camera itself (binning that moves the width, a setting
  that the camera adjusts).  Before, only the answer to a `set`, `settings`
  or `execute` could announce one.
- **Flir defaults for auto-exposure.**  The tree selects the `Ae` algorithm
  and turns off `AutoExposureTargetGreyValueAuto`; with the defaults of the
  camera, `ExposureAuto` `Once` changes nothing.  The Blackfly S leaves
  `ExposureAuto` at `Once` after it converges (SpinView does the same), so
  set it to `Off` to edit `ExposureTime` again.

### Fixed

- **A deadlock in `QGenicamCamera`.**  `node()`, `hasNode()` and the lookup
  of `states()` read the GenICam node map without the camera lock.  The
  `genicam` binding keeps the interpreter lock while it waits for the lock
  of the node map, so a thread that read the map while another wrote a
  setting (the capture thread of a remote camera that pushes states, or the
  interface that polls them) could deadlock with it: the process froze when
  the frame rate was set at a low frame rate.  Every access to the node map
  now holds the camera lock.
- The worker of a remote camera closes its sockets on exit; Python no longer
  reports an unclosed socket (`ResourceWarning`).

---

## [4.11.1] — 2026-10-31

### Fixed

- `python QCamcorder.py -h`, and every other application that starts with
  `launch`, stalled while it printed the help and crashed when it quit, and
  a bad value on the command line (`-c abc`) left the splash screen waiting
  for a camera that never came.  `launch` read the command line on the
  thread that opens the camera, where the `SystemExit` of argparse ended
  only the thread.  The command line is now read first, on the main thread:
  `-h` prints the options and ends, and a bad value ends with a message.

### Documentation

- Known issues: a GenICam camera read through harvesters freezes the other
  threads of the process, because the `genicam` binding does not release
  the interpreter lock (genicam/harvesters issue 508), with the
  measurements.  The plan to deal with it is in `TODO.md`.

---

## [4.11.0] — 2026-10-29

### Upgrading from 4.10

Code that imports the left column needs the right column.  Nothing has
an alias.

| 4.10 | 4.11 |
|---|---|
| `QVideo.lib.QHistogramWidget` | `QVideo.widgets.QHistogramWidget` |
| `QVideo.lib.QUniformityWidget` | `QVideo.widgets.QUniformityWidget` |
| `QVideo.lib.QScrollPanel` | `QVideo.widgets.QScrollPanel` |
| `QVideo.lib.choose_camera` | `QVideo.cameras.chooser.choose_camera` |
| `QVideo.lib.chooser` (`camera_parser`, ...) | `QVideo.cameras.chooser` |
| `QVideo.cameras.registry` | `QVideo.cameras.chooser` |
| `QVideo.interactive.camera.working` | `QVideo.cameras.chooser.working` |
| `camera.properties` (list of names) | `list(camera.properties)` |
| `camera._properties` (dict of specs) | `camera.properties` |
| `rack._registry()` | `rack.availableFilters()` |
| `QVideo.demos.ROIdemo` | `QVideo.demos.roidemo` |
| `QListCameras`, `QListCVCameras`, ... | `QCameraChooser` |
| `.example()` of reader, snapshot, screen, source | the demos |
| `DarkFrameFilter._dark`, `FlatFieldFilter._flat` | `.reference` |

### Added

- **A USB 3 camera on a slow link says so.**  A GenICam camera that
  reports `U3VCurrentSpeed` logs a warning when it opens at less than
  SuperSpeed.  A cable or port without the SuperSpeed wires lets the
  camera enumerate and answer commands, but its stream is slow and may
  stall, so that the first frame never arrives and the window freezes.
- **`ReferenceFilter` and `QReferenceFilter`: a pattern for calibration
  filters.**  A filter that corrects frames with a reference that the
  user captures needs only two methods, `_makeReference` (what the
  average of the captured frames makes of the reference) and `_correct`
  (how the reference corrects a frame); the base class averages the
  frames and has `capture()`, `reset()`, `nFrames`, `isCapturing`,
  `reference` and the `captured` signal, and its widget has the *frames*
  spinbox and the *Capture* and *Reset* buttons.  `DarkFrameFilter` and
  `FlatFieldFilter` and their widgets are built on them, which removes
  about 160 duplicated lines; the user guide shows how to write a third.
  The stored reference is `reference`, no longer `_dark` or `_flat`.

- **`QCameraChooser`: a combo box of the cameras that work.**  It lists
  what `available_cameras()` finds, looks on a thread of its own so that
  the window does not freeze while each device is opened, and emits
  `cameraSelected(model, cameraID)`, the arguments of `Camera()`, when the
  user chooses one.  It replaces the three camera-list widgets below.
- **`QOverlayWidget`: the base of an overlay's control widget.**  It runs
  the worker on a thread of its own, hands it one frame at a time, passes
  the results to the graphics item, shows or hides the item with the check
  box, and stops cleanly; a subclass supplies the worker, the graphics
  item and its controls, so the overlay in the user guide shrinks to a
  few lines.  `QTrackpyWidget` and `QYoloWidget` are built on it, which
  removes about 200 lines; their workers have the slot `process`, as the
  guide always said, and the trackpy worker has properties for its
  options instead of a dict that the widget wrote into.

### Changed

- **Breaking: three widgets and the chooser moved.**  `lib/` holds the
  base classes and the machinery that applications run on; the rest has
  a home of its own.  `QHistogramWidget`, `QUniformityWidget` and
  `QScrollPanel` are in the new `QVideo.widgets` package (finished
  widgets that nobody subclasses): import them with
  `from QVideo.widgets import QHistogramWidget`.  The command-line
  chooser is `QVideo.cameras.chooser` (`camera_parser`, `open_camera`,
  `make_tree`, `choose_camera`), and `QVideo.lib` no longer exports
  `choose_camera`.  `QSnapshot` and `launch` stay in
  `lib`.  The old import paths are gone, with no aliases.
- **`cameras` no longer depends on `interactive`, and choosing a camera
  is one module.**  `QVideo.cameras.chooser` holds the table of backends,
  the code that opens a camera from it (`create_camera`, `open_first`)
  and the command-line chooser; the separate `registry` module is gone.
  `Camera()` and the chooser both open cameras with `open_first`, and the
  chooser no longer builds a notebook proxy to get a camera.  Each entry
  of the table carries the command-line flag and help text of its
  backend, so adding a backend is one edit fewer.  `cameras` now imports
  only from `lib`.
- **`lib` loads without `filters`.**  `QFilterRackWidget` imports the
  filters when the rack first needs them, so `lib` imports no other
  QVideo package at load time but `cameras`, for `launch()`.
- **Breaking: the camera's property table and the table of backends are
  public.**  `QCamera.properties` is the dict of the registered
  properties, name to spec, that `QCameraTree` and the notebook widgets
  read; it replaces the private `_properties` and the old `properties`,
  which returned only the names (iterate the dict for them).  In
  `QVideo.cameras.chooser` the table is `BACKENDS` and the function that
  lists the importable candidates is `discover`, and
  `available_cameras()` and `working()` moved there from `interactive`;
  `QVideo.available_cameras` is unchanged.
- **`QCamera.aliases`: the shared names are a map, not properties.**  A
  backend whose properties have the names of a standard, such as GenICam's
  `Width`, lists `width`, `height` and `fps` in `camera.aliases`; they work
  as attributes and in `get`, `set` and `shape`.  The GenICam camera no
  longer copies them into `properties` and no longer overrides `settings`
  to hide them, so `settings` and `properties` have the same names on
  every backend, and the conformance suite checks it.  The backend guide
  shows how a new interface offers the shared names.
- **Breaking: `availableFilters()` returns the filters, not just their
  names.**  `QFilterRackWidget.availableFilters()` maps each display name
  to its widget class, sorted by name: iterate it for the names, index it
  for a class.  It replaces the private `_registry()`, which
  `Filter()` reached into; `Filter()` still lists the sorted names.
- **Breaking: `ROIdemo` is `roidemo`.**  The module is named like the
  other demos (`python -m QVideo.demos.roidemo`); the classes `ROIDemo`
  and `CropROI` keep their names.
- **`camera_parser` rejects a conflicting flag.**  A parser of the caller
  that already defines one of the camera flags now raises the
  `argparse` error instead of silently skipping it.

### Removed

- **Breaking: `QListCameras`, `QListCVCameras` and `QListFlirCameras`
  are gone.**  Nothing used them, and each listed the cameras of one
  backend; `QCameraChooser` lists the cameras of all of them.  `lib` no
  longer exports `QListCameras`.
- **Six `example()` methods.**  `QVideoReader.example` and
  `QVideoReader.examplevideo` (the sample video is in the documentation,
  which the installed package does not ship), `QSnapshot.example`,
  `QVideoScreen.example`, `QVideoSource.example` and
  `QListCameras.example` repeated what the demos show, were not tested,
  and made `lib` import the Noise camera.  `QCamera`, `QCameraTree`,
  `QVideoFilter` and `QFilterRackWidget` keep theirs, which
  `python -m QVideo.cameras.Noise._camera` and the filter modules use.

### Fixed

- **A camera tree listens again after a failed synchronization.**  The
  flag that stops a tree from echoing the camera's own changes back to
  it was reset by hand, so an error while the tree read the camera left
  the tree deaf to every later edit.  `QCameraTree._syncIgnored()`
  resets it however the block ends.
- **A GenICam camera that fails to open is released.**  A camera that
  failed after its device had opened stayed claimed, and every later
  open in the process found no camera.  The camera is now released
  however `_initialize` fails.

---

## [4.10.0] — 2026-10-28

### Added

- **A splash screen shows while the camera opens.**  `launch()` (so
  every demo and `python -m QVideo`) shows a splash screen at once, with
  the name of the application, the version and what is happening, and
  opens the camera on a thread of its own: a camera that takes seconds
  to open, such as a GenICam camera that reads its whole node map, no
  longer leaves the screen blank and frozen.  The window appears when
  the interface is built; if the camera cannot be opened the program
  ends with the reason.  The fringes are drawn when the splash screen
  appears, so the package ships no image.  `lib.chooser` has two new
  functions, `open_camera()` (no widget, so it is safe in any thread)
  and `make_tree()`; `choose_camera()` calls both.
- **Writers say why they stop.**  `QVideoWriter.finished` now carries a
  string: empty when the writer has the frames that it was asked for,
  otherwise an explanation.  A writer stops, once, when the size or type
  of the frames changes (a writer whose format can store such frames sets
  `fixedSize = False`), when the file cannot be opened or when writing
  raises an exception, instead of failing again with every frame.
  `QRecorder` and `QDVRWidget` report the explanation through `stopped`
  and end the recording.

- **`QSourceSelector`.**  `QVideo.dvr.QSourceSelector` is a group of radio
  buttons that chooses which source of frames to record: add each source
  with a name and connect `sourceChanged` to the recorder.  It is disabled
  while a recording runs, because a filter may change the size of the
  frames and a writer cannot follow.  `FilterRackDemo`, `CombinedDemo` and
  `CompositeDemo` use it, so `CompositeDemo` now has a Raw/Composite pair
  of buttons instead of a check box.

- **`available_cameras()`.**  `from QVideo import available_cameras` lists
  the cameras that work as `(model, cameraID, name)`, for example
  `('OpenCV', 0, 'FaceTime HD Camera')`; the first two items are the
  arguments of `Camera()`.

- **`Filter()`: find filters by name.**  `Filter()` lists the filters that
  QVideo provides and `Filter('Smoothing', 'Canny')` builds them from their
  display names, ignoring case and spaces, so that
  `camera.filters = Filter('Smoothing', 'Canny')` needs no imports.  A
  wrong name raises an error that suggests the nearest ones.

- **`camera.filters` in notebooks.**  The camera that `Camera()` returns
  has a list of filters that `read()` and `live_view()` apply to every
  frame, in order: `camera.filters = [DarkFrameFilter(), GammaFilter()]`.
  Any filter of `QVideo.filters` or any function of a frame will do; a
  filter that raises is reported and removed, and one that has no result
  yet makes `read()` take another frame.

- **Hardware timestamps for GenICam cameras.**
  `FrameInfo.hardware_timestamp` now holds the camera's own timestamp for
  each frame, in seconds, for every GenICam camera (Basler, FLIR, IDS, MV,
  VimbaX); it is `None` when the camera has no clock, and the HDF5
  recording stores it.  A camera subclass sets `QCamera.hardwareTimestamp`
  in `read()` and the source copies it into the frame's `FrameInfo`.

- **GenICam register nodes.**  The raw blocks of camera memory that a
  GenICam node map calls registers (lookup tables, user data, vendor
  structures) appear as read-only properties holding their bytes in
  hexadecimal, and as read-only text in `QGenicamTree`; a register longer
  than 256 bytes is reported by size and not read.  With these, every
  GenICam node type is covered.

- **`QRecorder` and `QPlayer`: recording and playback without a window.**
  A `QRecorder` writes the frames of a source to a file on a thread of its
  own, watches the backlog and stops when the writer falls behind
  (`stopWhenBehind`, `lagLimit` and `maxMemory`, as the DVR widget did); a
  `QPlayer` plays a file at its own frame rate, and its `source` can be
  given to a screen or a filter pipeline.  Both are controlled by plain
  method calls and signals and stop themselves when the application quits.
  Like any Qt object they rely on the event loop of the application; neither
  runs one of its own.  `QRecorder.start()` refuses to replace a file that
  exists (`FileExistsError`) unless called with `overwrite=True`; the DVR
  widget asks the user first.

- **`QScrollPanel`: controls that scroll.**  `QCamcorder` puts its panel of
  controls in one, so an application with many controls, such as
  `CombinedDemo`, no longer needs a window taller than the screen: the
  panel keeps its natural width and gets a vertical scroll bar only when
  the window is too short for it.

### Removed

- **`python -m QVideo.lib.gentl` is now `python -m QVideo.cameras.gentl`.**
  The GenTL diagnostic belongs with the cameras that use it.

- **`QVideo.lib.Camera` is gone.**  The notebook and script front door
  now has a package of its own, `QVideo.interactive`; import `Camera` and
  `Filter` from `QVideo`, as before.  The table of camera backends is
  `QVideo.cameras.registry`.

- **`QOpenCVSource`, `QPyAVSource` and `QHDF5Source` of `QVideo.dvr`.**
  Each was a `QVideoSource` made from a file name.  Any video file now
  gives a source with `QVideoSource(formats.openVideo(name))`, and
  `QPlayer` makes its own.  (`QVideo.cameras.OpenCV.QOpenCVSource`, the
  source of a camera, is not affected.)

- **`dvr.formats`: the file formats in one place.**  The tables `Writer`
  and `Reader` map a file extension to the class that writes or reads it;
  `fileFilter`, `writerClass` and `readerClass` look them up.  An
  unsupported extension is a `ValueError` that lists the supported ones.

- **Readers behave like sequences of frames.**  `formats.openVideo(name)`
  returns a reader that supports `len(video)`, `video[i]`, `video[a:b]` and
  iteration, with no thread, clock or Qt application, so the frames of a
  recording are available as arrays for analysis.

### Changed

- **`QVideoWriter.finished` carries a string.**  A slot of your own
  should take it: the reason that the writer stopped, empty if all is
  well.

- **`await Camera()` no longer asks about the simulated camera.**  A
  single real camera is opened without a question (it used to show a
  chooser for the camera and Noise), and Noise alone says that no hardware
  was found.  The chooser appears for two or more real cameras, with a
  line that says to press Open and what to do if the notebook shows
  `HBox(...)` instead of a drop-down.  The Jupyter chapter now recommends
  `%pip install "QVideo[pyqt6,jupyter]"` and explains how to get widgets
  drawn.

- **`QDVRWidget` is the control panel of a recorder and a player.**  It
  keeps the file dialogs and the questions to the user, and does the rest
  through `dvr.recorder` and `dvr.playback`.  Its signals are unchanged.
  The property `dvr.player` is gone: the source of the video being
  played is `dvr.playback.source`.
  The arguments `stopWhenBehind`, `lagLimit` and `maxMemory` still go to
  the constructor, but the attributes are those of `dvr.recorder`.
  The class attributes `Writer`, `Player` and `FileGroups`, and
  `_buildFilter`, are replaced by `formats.Writer`, `formats.Reader`,
  `formats.Groups` and `formats.fileFilter`; to record a format with
  another class, set `formats.Writer['.mkv'] = QOpenCVWriter`.  The
  `Player` table of sources is gone: playback uses the reader's class and
  a plain `QVideoSource`.

- **HDF5 files hold one dataset of frames, and survive a crash.**
  `QHDF5Writer` now writes `frames`, `timestamp`, `index` and
  `hardware_timestamp` arrays, instead of one dataset for each frame, in
  the single-writer, multiple-reader mode of HDF5, and flushes about once
  a second.  A file of the old layout could not be opened after the
  program was killed, and a long recording was lost whole; now the frames
  up to the last flush are kept, and another process can read the file
  while it is written.  The new layout also keeps the index and the
  hardware time of each frame, costs 16 bytes for a frame instead of 333,
  and opens a file of a million frames in milliseconds instead of seconds.
  The file says `format_version` 2.  `QHDF5Reader` reads both layouts, so
  old recordings stay readable, and has a `timestamps` property.  A frame
  of another size or type than the first ends the recording, as it does in
  the PyAV writer.

### Fixed

- **A GenICam camera shows live video.**  A producer hands out frames
  oldest first by default, so a reader a little slower than the camera
  kept a queue of old frames: with a FLIR camera the video lagged by
  about a second at the start and caught up over half a minute.  The
  camera now asks its stream for the newest frame, and a producer that
  cannot do this keeps its default.

- **The GenICam camera tree builds in a fraction of the time.**  Showing
  or hiding a row made the tree read every setting of the camera again,
  once for each row: 64,000 reads and 6.6 s for a FLIR camera.  Showing
  rows reads nothing now, and the tree builds in 0.5 s.

- **The GenICam camera tree no longer freezes the interface.**  The
  tree polled every visible node from the GUI thread, one request for
  the lock each, while the capture thread held the lock to wait for its
  next frame: with a FLIR camera the window stalled for seconds (a
  spinning beach ball on macOS) and the capture thread was starved.  The
  tree now asks `QGenicamCamera.states(names)` for many nodes at once,
  under one hold of the lock, reads 32 parameters per poll (the poll
  runs every 0.2 s and cycles through them), and refreshes limits,
  values and enabled states from the same snapshot.  `state()` also
  reports `writable`.
- **Composite recording works.**  The rendered scene that a screen emits
  in `composite` mode had four channels (RGBA), which the PyAV writer
  refused ("Unexpected numpy array shape"), so recording from
  `CombinedDemo` or `CompositeDemo` failed.  It now has three, like every
  color frame.

- **`Camera()` no longer loses the application it makes.**  When a
  script or notebook had no `QApplication`, `Camera()` made one without
  keeping a reference, so Python deleted it again at once and anything
  that built a widget afterwards stopped with "Must construct a
  QApplication before a QWidget".  The application now lives as long as
  the process.

- **The first recording of a session no longer stops itself.**  `av` was
  imported when the first frame arrived, which held up the writer for a
  second or more on a cold start, so a camera at full rate piled up
  enough backlog for the recorder to give up after a few frames.  The
  writer now imports PyAV when it is made, before any frame is sent.

- **The reason that a recording stops no longer advises HDF5.**  On a
  FLIR camera at 1280 by 1024, HDF5 fell further behind than FFV1 or
  H.264; the message now suggests PyAV, if it is missing, and a lower
  frame size or rate.

---

## [4.9.0] — 2026-10-27

### Changed

- **`QCircularDVRWidget` saves on a thread of its own.**  A large buffer
  used to hold up the interface, and so the camera's display, while it was
  written.  Now the **Save** button is disabled while the file is written,
  `saved` is emitted when it is done, and the frames that are written are
  those that the buffer held when **Save** was clicked.  Quitting the
  application, or deleting the widget, waits for a save in progress.

- **`QDVRWidget.pause()` only pauses, and `play()` resumes.**  `pause()`
  used to toggle between pausing and resuming; the play button, which does
  that, is a toggle of its own.  The slot `setFrameNumber` is private
  (`_setFrameNumber`), like the other slots of the Qt classes.

- **The recording watchdog is a class of its own.**  `QBacklogMonitor`
  measures how far the writer of a recording has fallen behind the camera
  and emits `backlog` and `behind`; `QDVRWidget` forwards both signals and
  decides whether to stop (`stopWhenBehind`).  The widget's signals and its
  `stopWhenBehind`, `lagLimit` and `maxMemory` are as before, except that
  the limits are read when a recording starts, not with every frame.

- **`QCircularBuffer` only buffers; `QCircularDVRWidget` saves.**  The
  buffer had its own HDF5 writer, a copy of `QHDF5Writer` without its
  compression, and wrote video through OpenCV alone.  It now stores each
  frame with its `FrameInfo` and offers `frames()` and `actualFps` (the rate
  of the buffered frames, from their capture times); `QCircularBuffer.save`
  is gone.  The widget writes the buffer with the writer that
  `QDVRWidget.Writer` has for the extension, so the circular DVR now uses
  PyAV when it is installed, compresses HDF5 and writes 16-bit gray, like
  the recorder, and any writer that a user registers works too.  HDF5 files
  are keyed by the monotonic capture time, as the recorder's are.

- **The Jupyter code is in one module.**  `live_view`, the camera chooser
  that `await Camera()` shows, and `controls` are implemented in
  `lib/_jupyter.py`, the only module that needs `ipywidgets`.
  `lib/_camera.py` is now the plain headless factory and imports the
  notebook module only when a notebook feature is used, so `Camera()` works
  without `ipywidgets`.  Behavior is unchanged.  The live-view handle is
  `QVideo.lib._jupyter.LiveView` (it was the private `_LiveView`).

- **`QGenicamCamera.has_node` and `is_readwrite` are now `hasNode` and
  `isReadWrite`**, like the other methods of the Qt classes.  The old names
  are gone.  (The `has_node` of genicam's own node map is unchanged.)

- **The reason for stopping a slow recording says what to try.**  The
  message was "recording fell 1.0 s behind the camera".  It now goes on:
  record to HDF5, install PyAV (`QVideo[av]`) when it is missing, or lower
  the frame size or rate; for a recording to HDF5, use a faster disk.  The
  message goes to the log and to `stopped(reason)`, which `QCamcorder` shows
  in its status bar.

### Fixed

- **A library that is installed but fails to import is no longer reported
  as missing.**  `QTrackpyWidget` and `QYoloWidget` said "trackpy is
  required ... Install it with pip" when the package was installed and
  something it needs (numba, torch) failed to load.  The error now carries
  the real one as its cause, so the traceback shows what to fix.
- **The Jupyter camera controls say when a setting fails.**  Changing a
  widget whose setter raised, such as a value that the camera refuses, was
  swallowed and the widget kept showing the value that was never applied.
  It is now logged as a warning that names the property.  A value that
  cannot be shown when the controls refresh is logged at the DEBUG level.
- **`Camera.live_view()` says why the feed stopped.**  A failed read ended
  the feed without a word; it is logged as a warning.
- **A Raspberry Pi camera whose model name cannot be read says why** at
  the DEBUG level.

---

## [4.8.0] — 2026-10-26

### Added

- **An `opencv` extra** installs `cv2-enumerate-cameras`, which gives the
  USB cameras their names.  QVideo has used it when it is installed, but
  did not declare it; without it the cameras are listed as "Camera 0" and
  so on.  The `trackpy` extra keeps `numba`: QVideo does not import it, but
  trackpy finds features about five times faster with it.
- **PyAV reader and writer** (`QPyAVWriter`, `QPyAVReader`, `QPyAVSource`),
  installed with the `av` extra.  `QDVRWidget` uses them for `.avi`,
  `.mkv` and `.mp4` files if PyAV is installed, and OpenCV if not.  FFV1
  in PyAV is several times faster than in OpenCV, so a 5-megapixel mono
  camera at 30 frames/s, which OpenCV could not record, keeps up; color
  files are half the size of those of HuffYUV.  The frames are compressed
  without loss and 16-bit gray frames are written too, which OpenCV cannot
  do.  Seeking is exact in lossless files and lands on the right frame in
  `.mp4` files.  `av` is imported when the first file is opened.  On macOS,
  PyAV and OpenCV each carry a copy of the FFmpeg library, which makes the
  system print a one-time warning that both define a class; QVideo does not
  use the part of FFmpeg that clashes.  To use OpenCV although PyAV is
  installed, set the `.avi`, `.mkv` and `.mp4` entries of
  `QDVRWidget.Writer` and `QDVRWidget.Player` to the OpenCV classes.
- **A camera that fails to open logs where it failed.**  The camera factory
  reported only the message of the exception, so a failure inside a camera
  library (as with FLIR and `genicam` 1.6) could not be located.  It now
  logs the traceback at the DEBUG level, and probing no longer silences
  the log when debug logging is on.  The quickstart shows how to turn it
  on.
- **A documented way to shut down.**  `QTrackpyWidget` and `QYoloWidget`
  have a public `stop()` (it was a private `_cleanup`) that ends the worker
  thread and can be called twice; they also stop their thread when they are
  deleted.  The architecture chapter has a "Shutting down" section that
  lists the `stop()` of each component and the order in which to stop them
  when an application removes part of its interface.  A regression test
  runs both ways in a subprocess.
- **`QVideoSource.seek(framenumber)`.**  Reads the given frame next, even
  while the source is paused.  The capture loop does the seeking between
  two reads, so the reader is never touched while it is reading.

### Changed

- **HDF5 recordings are compressed without loss.**  `QHDF5Writer` takes a
  `compression` argument.  The default, Zstandard, needs `hdf5plugin` (now
  in the `dvr` extra) and is used if it is installed; `'lz4'`, `'blosc2'`
  (best for 16-bit data), `'lzf'`, `'gzip'` and `None` are the other
  choices.  Reading a compressed file needs `hdf5plugin` as well, and the
  reader says so when it cannot decode a file.  Every filter returns every
  pixel, at 8 and 16 bits.
- **The DVR panel is a deck.**  One row of icon buttons (record, stop,
  first frame, one frame back, play/pause, one frame forward), a position
  slider, the frame and time read-outs, the file and the duration and
  interval of a recording.  The play button turns into a pause button
  while a video plays.  The slider follows the video and seeks when moved;
  while recording it shows how far the recording has come.  Playback
  pauses at the end of the video, and play then starts over.
  `QDVRWidget` has one file name for recording and playback: `playname`,
  `saveEdit`, `playEdit`, `pauseButton` and the `save` argument of
  `getFileName` are gone (`fileEdit` and `getFileName()` replace them), the
  frame counter is the slider (`framenumber` is read-only), and `seek()`
  and `step()` are new.  The panel warns before it plays a file that does
  not exist, and before it records over a file that cannot be written; it
  asks before it replaces a file that exists.
- **With OpenCV, color recordings to `.avi` and `.mkv` use HuffYUV, gray
  ones FFV1.**  Both are lossless, and HuffYUV encodes color frames several times faster,
  so a recording of a full-resolution color camera keeps up.  HuffYUV is
  not used for gray frames: through OpenCV it changes their values (by up
  to 2 gray levels), and it was the fallback for them when FFV1 was
  missing.  A gray recording on a build without FFV1 now fails with a
  warning and does not use it.  Tests write and read frames back and
  compare every pixel.
- **The DVR buttons use the icons of the Qt style**, drawn in the color of
  the button text so that they show on a dark theme, and the record button
  the Tango icon in `dvr/icons/record.svg` (Qt has no record icon; it is
  part of the package data, and the button shows the word "Record" if Qt
  has no SVG support).  The compiled resource `icons_rc.py` is gone.
- **Opening a GenICam camera is quiet.**  Loading the node map by hand,
  which `genicam` 1.6 with some producers always needs (as with the FLIR
  camera), is logged at the DEBUG level and no longer as a warning.  A
  node map that cannot be loaded still stops the open with an error.
- **Recording every Nth frame is documented as a time-lapse.**  The file
  declares the frame rate of the source, so it plays back N times faster;
  HDF5 files keep the capture time of each frame.  The tooltip of the
  interval control and the `nskip` documentation say so.

### Fixed

- **Recording no longer asks the camera for the frame rate with every
  frame.**  The backlog watch of `QDVRWidget` read `source.fps` for each
  captured frame.  The read takes the camera lock, which a camera holds
  while it waits for its next frame, so the GUI thread spent a large part
  of its time waiting for the camera, and a recording could fall behind.
  The rate is now read once, when the recording starts.
- **`QVideoScreen` ignores a shape of -1.**  A driver can report -1 for
  the frame size before the stream runs (macOS with OpenCV); the screen
  then asked Qt for a negative minimum size and Qt warned
  "Negative sizes (-1,-1) are not possible".  It treats any shape that is
  not positive as unknown, as it already did for zero.
- **Stopping playback waits for the thread that plays.**  The video file
  is closed when `QDVRWidget.stop()` returns, so the file can be recorded
  over at once, and Qt no longer prints "Thread tried to wait on itself".
- **Recording through `ROIDemo`'s ROI keeps the capture information.**  The
  demo's crop dropped the `FrameInfo` of each frame, so the recorder lost
  the capture times and the backlog watch of `QDVRWidget` for ROI
  recordings.  The crop now passes it on, and is a copy, so the recorder's
  queue holds the cropped pixels and not the whole camera frame (the
  memory budget counts the cropped size).  The demo's ROI class is renamed
  `CropROI` (it was `ROIFilter`, the name of the unrelated crop filter in
  `QVideo.filters.roi`).

---

## [4.7.1] — 2026-10-26

### Fixed

- **GenICam cameras (FLIR) could not be opened with `genicam` 1.6.**
  When the Spinnaker producer hands over a node map that harvesters has not
  connected to the camera, `QGenicamCamera` loads the map by hand.  It
  decided that by asking the map for `Root`.  Older `genicam` answers
  `False` for an unconnected map, but version 1.6 raises `AccessException`
  ("Feature not present (reference not valid)"), so the open failed before
  the fallback ran.  Either answer now leads to the fallback.

---

## [4.7.0] — unreleased

### Added

- **`QCamera.actualFps`**, the frame rate that the camera delivers, beside
  `fps`, the rate that was asked for, as in GenICam.  It is read-only and
  equals `fps` unless a backend knows better: `QGenicamCamera` reads
  `AcquisitionResultingFrameRate` (or `ResultingFrameRateAbs` or
  `ResultingFrameRate` on older firmware) and falls back to `fps`.
  `QVideoSource.fps` now reports it, so the file header of a recording, the
  memory budget of the DVR, the circular buffer and the screen use the rate
  at which frames arrive.  `QVideoReader` has the same property, equal to
  its `fps`.  OpenCV cameras use the rate that the driver reports, which
  QVideo does not second-guess.

### Changed

- **The demos read as recipes.**  Each one overrides `_setupUi()`, calls
  `super()._setupUi()` first, and then builds its widgets, connects them
  and adds them to `self._controls`, the layout of the panel of controls,
  which `Demo` and `QCamcorder` now both provide.  Each class docstring
  gives a one-line summary and a `Data flow::` sketch of where the frames
  go, and the parameters are documented once, in the base class.
  `tests/test_demo_recipes.py` keeps them that way.
- **The demos page of the documentation** explains the recipe pattern, lists
  the demos as a ladder of ideas, and shows the `_setupUi()` of each demo
  straight from the source, so it cannot drift.  It now covers the
  histogram, uniformity and circular-buffer demos, which it had missed.
- `QCamcorder` and `Demo` connect the camera to the screen (and the
  recorder) inside `_setupUi()`, so that a recipe can replace the source
  of the screen after calling `super()._setupUi()`.  `Demo` and `QCamcorder`
  subclasses that set the source in `__init__` keep working.

### Fixed

- **A video larger than two thirds of the screen opened in a window of the
  wrong shape.**  An application builds the screen, and the camera reports
  its shape, before the screen is in its main window, so the fit to the
  video resized the widget itself and the main window opened at Qt's
  default size, which is capped at two thirds of the screen.  A 1280x720
  camera on a laptop then showed black bars above and below the image.
  `QVideoScreen` now fits the window when it is first shown, unless the
  application or the user has already sized it.  It also sets the view
  range after every fit, which a window that could not take the new size
  had left stale.

---

## [4.6.0] — 2026-10-25

### Added

- **`QDVRWidget.backlog(fraction)`** reports how far a recording has fallen
  behind the camera, as a fraction of what is allowed (`1.` is the point at
  which `behind` is emitted), in steps of 5% so that it never floods the
  interface.  An application can warn before anything is lost, and see
  what `lagLimit` and `maxMemory` should be.
- **`QCamcorder.message(str)`** carries what the user should know about the
  recording: the backlog once a recording is a quarter of the way to
  falling behind, and, when the DVR stopped the recording by itself, why.
  The host decides where to show it.

### Changed

- **`launch()` shows the application in a `QMainWindow`**, as real
  applications embed QVideo components, so that sizing and shutdown are
  exercised in that setting.  The window is titled, closes on Ctrl+Q, and
  its status bar shows the `message(str)` signal of a widget that has one,
  such as `QCamcorder`.  `tests/test_mainwindow.py` shows every
  application as the center of a main window at several video shapes and
  resizes it.
- **The control column is more compact**, so the video, not the controls,
  sets the height of a window and the black bars above and below it shrink.
  `QCameraTree` asks for 120 pixels of height, instead of its preferred
  196, and takes the height that its neighbors leave, the screen and
  controls use 4-pixel margins and 3-pixel spacing, and the record-mode box
  of `FilterRackDemo` is flat.  `FilterRackDemo` and `CombinedDemo` need
  about 110 pixels less height and 20 pixels less width.

---

## [4.5.1] — 2026-10-25

### Changed

- **A `QFilterRack` shuts its pipeline down by itself.**  The pipeline
  already stopped when the application quit; it now also stops when the rack
  is deleted, so `FilterDemo` and `FilterRackDemo` no longer override
  `closeEvent` to stop it.  Closing a window only hides a rack, so an
  application that outlives its window can still call
  `rack.pipeline.stop()` to stop the thread sooner.
- `FilterRackDemo` chooses the recording source from a dictionary of
  mode buttons instead of an if/elif chain, and `CombinedDemo` adds its
  Composite button to the same dictionary.

---

## [4.5.0] — 2026-10-25

These changes are made as if they had been part of 4.0.0, which was released
days ago: there are no deprecated aliases.

### Added

- **`QFilterRack` now owns the pipeline that runs its filters.**
  `QFilterRack(source=camera)` creates a `QFilterPipeline` that follows the
  rack on a worker thread, so a slow filter cannot stall the interface or the
  camera and a rack that falls behind keeps the newest frame.  Connect
  consumers to `rack.pipeline`; `rack.source` forwards to the pipeline's
  source.  A single call replaces the rack-plus-pipeline wiring that
  `FilterDemo` and `FilterRackDemo` repeated, and the demos no longer need
  their own pipeline attribute.
- **`QFilterRackWidget`** is the thread-free panel that `QFilterRack` used to
  be.  Calling it applies the filters in the caller's thread, which suits
  recorded frames and designing or exporting a pipeline without a camera.

### Changed

- **`QFilterStack` is now `QFilterPipeline`** (module `lib/QFilterPipeline.py`),
  because it applies a pipeline of filters; "stack" was ambiguous.  The class
  is otherwise unchanged and accepts a `QFilterRackWidget` or a
  `QFilterRack` through `rack=`.  Code that constructs its own pipeline for a
  rack still works; the rack's own pipeline then sits idle.
- `FilterDemo`, `FilterRackDemo` and `CombinedDemo` reach their pipeline as
  `demo.rack.pipeline`.

### Removed

- **`QFPSMeter`.**  Nothing used it, and the frame rate it estimated is
  already available from the timestamps in `FrameInfo` (see
  `QCircularBuffer`).

---

## [4.4.0] — 2026-10-25

### Added

- **`QVideo.lib.launch(widget, title, **kwargs)`** runs a camera
  application: it chooses the camera from the command line, shows the
  window, closes it on Ctrl+Q and ends with the message when an optional
  package is missing.  Each demo and `QCamcorder` repeated this startup
  by hand; each is now one call.  An application of your own can use it
  the same way.
- **`CombinedDemo`** (`python -m QVideo.demos.combineddemo`) is a recipe
  for an application that combines filters, a trackpy overlay and
  composite recording.  The overlay detects particles in the filtered
  stream, and a fourth recording mode saves the rendered scene.

### Fixed

- The quickstart's camera-controls example called a constructor that no
  longer exists, and both examples connected the source to the screen in a
  way that bypassed `QFrameRelay`.  They now run, and a test runs them.
- `docs/api/lib.rst` lists `QFrameRelay`, and `docs/api/demos.rst` no
  longer shows the removed `-r` camera flag.

---

## [4.3.0] — 2026-10-25

### Added

- **A busy GUI thread no longer buffers the video stream.**  The screen
  received every frame through a queued connection, so while the GUI
  thread was blocked (a modal dialog, a window drag) the frames piled up in
  its event queue: three seconds of a 200 fps, 2048 x 2048 camera held
  1.5 GB.  `QVideoScreen` now receives frames through the new
  `QFrameRelay`, which keeps only the newest frame and wakes the GUI
  thread at most once, so the same stall holds about 13 MB and the last
  frame shown is as fresh as before.  The relay runs in the capture thread
  and never blocks it.  Consumers that need every frame, such as the
  recorder, keep their direct connection to the source.

---

## [4.2.0] — 2026-10-25

### Added

- **A recording also stops before it fills memory.**  `QDVRWidget` takes
  `maxMemory`, the bytes that frames waiting for the writer may occupy.
  The default is 80% of the memory available when recording starts.  The
  budget is converted to the time the camera needs to fill it, so it joins
  `lagLimit` as one limit: whichever is smaller decides when the recording
  is behind.  `psutil` is now a dependency; it reads available memory the
  same way on Linux, macOS and Windows.

### Fixed

- A source or filter stack that the garbage collector frees no longer
  touches a Qt object whose C++ side is already gone, which crashed the
  test suite on Python 3.11.  The finalizers now ask Qt whether the
  thread is running.
- Exporting a filter pipeline writes UTF-8 on every platform (Windows
  used its locale encoding).
- `QCircularBuffer` reads total memory through `psutil` alone; the
  `os.sysconf` fallback does not exist on Windows.

---

## [4.1.0] — 2026-10-25

### Added

- **A recording stops when storage cannot keep up.**  A recorder must not
  drop frames, so frames queued in memory when storage was slower than the
  camera, and nothing said so: a writer needing 10 ms per frame fell a
  second behind a 150 fps source in two seconds and held about 200 MB.
  `QDVRWidget` now compares the capture time of each frame the camera
  delivers with that of the newest frame the writer has taken up, which
  also catches a writer stuck inside a single write.  Past `lagLimit`
  (default one second) it emits `behind(lag)` once and, by default
  (`stopWhenBehind=True`), logs the reason, emits `stopped(reason)` and
  stops, so a slow disk cannot fill memory.  Pass `stopWhenBehind=False`
  to record through the backlog.
- **Stopping a recording keeps every captured frame.**  The widget used to
  end the writer's thread at once, which discarded frames still waiting
  (20 of 238 in one test).  `QVideoWriter.shutdown()`, queued behind the
  waiting frames, now closes the file and ends the thread, and the writer
  closes its file in its own thread.  `QVideoWriter.received` holds the
  capture metadata of the newest frame it has been handed.
- **A "Frame delivery" section in the architecture guide** states the four
  delivery policies and which consumer follows which.

### Fixed

- The architecture guide said the screen emits the *filtered* frame; the
  screen has applied no filters since 4.0.0.

---

## [4.0.1] — 2026-10-25

### Fixed

- **Dropping a running `QVideoSource` aborted the process.**  Qt
  terminates the application when a `QThread` is destroyed while it is
  running, so a source that went out of scope without `stop()` crashed
  the interpreter.  The source now stops and joins its thread when it is
  garbage collected, as `QFilterStack` does.
- **Device access could overlap a frame read.**  `shape`, `settings` and
  `camera.width` called the registered getters without the camera mutex,
  so they could run during a `read()`; OpenCV on macOS (AVFoundation)
  answers such a query with -1.  `QCamera` now wraps every registered
  getter, setter and method in one reentrant lock, and `saferead` holds
  it for each frame, so every route to the device is serialized for every
  backend.  A setter may now read other properties and `read()` may call
  them.  `QGenicamTree`, which polled the node map from the GUI thread,
  now asks the camera for a snapshot (`QGenicamCamera.state`) that is read
  under the lock.
- **The Qt camera tree ignored `hidden` properties.**  A property
  registered with `hidden=True` is now invisible in `QCameraTree`, as it
  already was in the Jupyter controls.  The OpenCV tree no longer lists
  `width`, `height` and `fps` beside the `resolution` drop-down that sets
  them.
- **Stale `-r` flag.**  `QCamcorder` and the quickstart listed a `-r`
  option that does not exist; the quickstart now shows `-v` for VimbaX.

---

## [4.0.0] — 2026-10-25

### Added

- **`QFilterStack`: filters on a worker thread.**  It sits between a source
  and its consumers, runs the filters in order on one thread of its own,
  and emits `newFrame(ndarray, FrameInfo)` with the unchanged `FrameInfo`,
  so processed frames keep the capture time and index of the frames they
  came from.  It stands in for a `QVideoSource` (`newFrame`,
  `shapeChanged`, `fps`, `shape`), so a screen and a recorder can share
  one filtered stream.  With `depth=1` (the default) it always processes
  the newest frame and counts the frames it skips (`framesDropped`); a
  larger `depth` keeps a bounded queue for recording.  A filter that
  raises is logged, removed and reported (`filterFailed`).  With
  `rack=QFilterRack(...)` it follows the rack's switched-on filters and
  switches off the widget of a filter that fails.
- `QFilterRack.activeFilters()`, `QFilterRack.filtersChanged` and
  `QFilterRack.switchOff()`, and `QVideoFilter.switchOff()`.

### Changed

- **`VideoFilter.process()` is the hook for a stateless filter.**
  `get()` returns `process(self.data)`, so a filter that transforms each
  frame independently overrides only `process`; a filter that keeps state
  across frames still overrides `add` and `get`.
- **`QVideoScreen.setImage(image, info=None)` and
  `newFrame(ndarray, FrameInfo)`.**  The screen passes each frame's
  `FrameInfo` on with its `newFrame`, so recordings made from the screen
  (the "Display" mode of `FilterRackDemo`, composite recording) carry true
  capture times.  `setImage`, `QVideoWriter.write` and
  `QCircularBuffer.append` accept signals with or without the `FrameInfo`.
- **`QFilterStack` takes no Qt parent.**  It owns a running thread, which
  Qt would otherwise delete behind Python's back and abort the process;
  keep a reference to the stack.  It stops on `stop()`, at application
  exit, and when the last reference is dropped.

- **Faster filters, with no new dependency.**  Measured at 1080p color:
  the color-to-gray conversion that `SobelFilter`, `LaplacianFilter`,
  `ThresholdFilter`, `DoGFilter`, `CircleTransformFilter` and
  `QUniformityWidget` used cost about 15 ms (`image.mean(axis=2)`) and
  now costs 0.1 ms (`QVideo.lib.imageops.grayscale`, a single
  `cv2.cvtColor`); `ThresholdFilter` goes from 15.4 to 0.2 ms,
  `LaplacianFilter` from 16.1 to 0.8 ms, `DoGFilter` from 17.1 to 3.2 ms
  and `SobelFilter` from 21.6 to 6.2 ms.  `ExposureFilter`'s Log and
  Sigmoid modes now apply a lookup table, 26.8 to 0.3 ms, with output
  identical to the old per-pixel formula, and `Normalize` divides by the
  background without the slow masked ufunc path, with identical output.
- **Color frames are converted to gray by luminance, not by the plain
  channel mean.**  `0.299 R + 0.587 G + 0.114 B` replaces
  `(R + G + B) / 3` in the filters above, in their exported `to_code`
  fragments, and in `QUniformityWidget`.  The two agree for a monochrome
  sensor whose image is replicated into three channels, and differ for a
  true color camera (by up to 65 gray levels for saturated colors).
- **`FilterRackDemo` now uses one `QFilterStack`.**  The old demo applied
  the same rack twice, once per camera frame in a tap that stayed
  connected in every recording mode and again per displayed frame as
  `screen.filter`, so stateful filters saw two interleaved streams and the
  GUI thread did full-rate work even when nothing was recording.  The
  display and the recorder now share the stack's output, and DVR playback
  is filtered by pointing the stack at the player.

- **`QVideoSource.newFrame` is now `newFrame(ndarray, FrameInfo)`.**
  `FrameInfo` (new, in `QVideo.lib.videotypes`) carries the frame's
  `index`, a monotonic capture `timestamp` taken in the capture thread
  immediately after `read()`, an optional `hardware_timestamp`, and a
  `wallclock` property.  Existing one-argument slots, lambdas and
  signal-to-signal connections keep working unchanged (tested on PyQt5
  and PyQt6).
- **Recordings are time-stamped at capture, not at write.**
  `QHDF5Writer` keys each frame by the elapsed capture time and sets the
  file's `Timestamp` attribute to the capture time of the first frame;
  `QCircularBuffer` stores capture times.  Previously both used the time
  at which the frame reached the writer, which lagged capture whenever
  the writer fell behind.
- `QVideoWriter.write(frame, info=None)` and the abstract
  `QVideoWriter._write(frame, info)` take the capture metadata.  Custom
  writer subclasses must accept the new `info` argument in `_write`.
- Python 3.10 is no longer supported; the package now requires
  Python 3.11 or later and is tested on 3.11 through 3.14.

- **Documentation examples for filtering used methods that do not exist**
  (`QFilterBank.addFilter`, `updateFrame`, and a `newFrame` signal on the
  bank); they now show `QFilterStack`.
- **Optional packages are no longer imported until needed.**  `import
  QVideo` takes about 0.2 s instead of 0.9 s because scipy, which only
  `CircleTransformFilter` uses, is imported when that filter is created;
  scipy is no longer a core dependency (`pip install
  "QVideo[circletransform]"`).  `QVideo.overlays` imports its submodules on
  first use, so the trackpy overlay no longer loads ultralytics and PyTorch.
- **Optional dependencies are split by feature.**  The `overlays` extra is
  now the union of `trackpy` (trackpy, pandas, numba) and `yolo`
  (ultralytics).  The `dev-pyqt5` and `dev-pyqt6` extras no longer install
  ultralytics and PyTorch (53 packages instead of 79); `dev` still does.

- **PyQt6 is the recommended Qt binding.**  Bindings remain optional extras
  (a hard dependency cannot defer to a binding that is already installed,
  and would break Raspberry Pi systems that use the system packages), but
  `import QVideo` without one now raises an `ImportError` that names the
  extras to install instead of qtpy's bare "No Qt bindings could be found".
  Added the `pyside6` extra; PySide6 is experimental.  CI now
  runs PyQt6 on every supported Python version, PyQt5 on the oldest and
  newest, and PySide6 as an allowed-failure job.

### Removed

These removals complete the move of filtering to `QFilterStack`.  To
migrate:

- **`QVideoScreen.filter` is gone; the screen applies no filters.**
  Put a `QFilterStack` in front of the screen and display it:
  `stack = QFilterStack(source, [SmoothingFilter()])` then
  `screen.source = stack` (or `QFilterStack(source, rack=rack)` for a
  `QFilterRack`).  The display and any recorder now share one filtered
  stream, and filters run on a worker thread.
- **`QFilterBank` is removed.**  Use `QFilterRack` (`editable=False` for a
  fixed panel) with a `QFilterStack`; `rack.addByName('Smoothing')`
  replaces `bank.registerByName('QSmoothingFilter')` and takes the display
  names shown in the rack's picker.
- **`AsyncVideoFilter` and `VideoFilter.shutdown()` are removed.**  No
  filter owns a thread any more.  `BlobFilter`, `CartoonFilter`,
  `CircleTransformFilter`, `DejitterFilter`, `ExposureFilter`,
  `ForegroundEstimator`, `PencilSketchFilter` and `SmoothingFilter` are
  plain `VideoFilter` objects; run them in a `QFilterStack` to keep them off
  the GUI thread.  Their `get()` now raises `RuntimeError` before the first
  `add()`, like the base class, where it used to return `None`.
- **`FilterDemo(cameraTree, filters)`** takes display names such as
  `'Smoothing'` and `'Canny'` instead of class names such as
  `'QSmoothingFilter'`.

### Fixed

- **`QCamcorder -c` showed the wrong resolution.**  The OpenCV camera
  control tree's resolution dropdown showed 640×480 (its first entry) while
  the camera was delivering another resolution, and it jumped back to the
  first entry whenever any other setting changed.  The dropdown held
  `(width, height, fps)` tuples while the camera's `resolution` property
  uses label strings, and every tree sync wrote the label into the tuple
  list.  `QCameraTree` now builds a drop-down from any `str` property that
  has `limits` (as the Jupyter interface already did), and `QOpenCVTree`
  uses the camera's own `resolution` property instead of a parallel
  tuple-valued control, which also removes about 45 lines.
- **A filter that raises now switches itself off instead of breaking the
  pipeline.**  `QVideoFilter` logs the error once, unchecks itself (with
  the error in its tooltip) and passes frames through unchanged; checking
  it again retries.  Previously a synchronous filter's exception was raised
  from `QVideoScreen.setImage` on every frame, freezing the display, and an
  asynchronous filter whose `process()` raised in its worker thread never
  became ready again and silently stopped accepting frames.
  `AsyncVideoFilter` now hands the exception to the consumer: `get()`
  re-raises it once, in the calling thread, and the filter stays ready for
  the next frame.
- **`BlobFilter` accepts color frames.**  It passed them straight to
  `cv2.connectedComponents`, which needs one channel, so on a color camera
  it raised on every frame (and, by the bug above, then stopped).  A color
  frame is now treated as a mask: a pixel is foreground if any channel is
  nonzero.
- **`QOpenCVCamera.resolution` no longer reports the smallest format when
  the device size is not in the probed list.**  It now reports the nearest
  probed format (an exact match when there is one) instead of silently
  falling back to the first, smallest entry.
- **PySide6 compatibility of the core classes.**  `QCamera`,
  `QVideoReader` and `QVideoWriter` now share one metaclass, `QABCMeta`
  (`QVideo.lib._qabc`), instead of three identical definitions; it lists
  `ABCMeta` before the `QObject` metaclass, and `QCamera.__setattr__` calls
  `super().__setattr__`.  Under PySide6, `isinstance(x, QCamera)` raised
  `AttributeError` (breaking `QCameraTree` and the camera chooser), and on
  Python 3.12 and earlier every camera constructor raised `TypeError`.
  PyQt behavior is unchanged.  The `pyside6` extra requires PySide6 6.7 or
  later, the first series in which this class layout works.
- **Recording every Nth frame (`nskip` > 1) wrote a single frame.**
  `QVideoWriter.write` decided whether to record a frame from the count of
  frames already written, which stopped advancing after the first write, so
  no later frame was ever recorded.  `QVideoWriter.framenumber` now counts
  frames received, and `nskip=N` records every Nth frame as the DVR
  widget's "Record every Nth frame" control promises.
- **`QVideoSource.resume()` could be lost, leaving capture stalled.**  If
  `pause()` and `resume()` both arrived while a frame read was in flight
  (for example during a long exposure), the wake-up was sent before the
  capture thread started waiting, and the thread then blocked until
  `stop()`.  `resume()` now clears the paused state under the mutex, so
  `isPaused()` is also accurate immediately afterward.
- **The first frame of a recording was discarded.**  It was used only to
  open the output file; it is now recorded like every other frame.

---

## [3.19.0] — 2026-10-23

### Changed

- **GenICam backends report why a camera cannot be opened** — a missing
  `GENICAM_GENTL64_PATH`, a producer `.cti` that is not on that path, a
  producer that fails to load, and a missing camera now raise
  `QDriverError` / `QDeviceError` (subclasses of the new `QCameraError`)
  with an actionable message instead of logging a warning and leaving the
  camera closed.  `Camera()` and `choose_camera()` include each backend's
  reason when no camera can be opened or when they fall back to the
  simulated camera, and `Camera('flir')` reports the import failure when
  `harvesters`/`genicam` are missing.
- Spinnaker 4.3.0.189 warning replaced by a note that 4.4.0 fixes it.

### Added

- `python -m QVideo.lib.gentl [producer.cti ...]` — step-by-step GenTL
  diagnostic that works without `harvesters`/`genicam` installed.

### Fixed

- `QListFlirCameras` called `QFlirCamera.producer()` on a `None` class
  attribute and raised `TypeError`; it now resolves the producer and logs
  a warning if it cannot be found.
- `QBaslerCamera` and `QMVCamera` looked for their producer when the module
  was imported, so setting `GENICAM_GENTL64_PATH` afterward had no effect.
  They now resolve it when the camera is opened, like the other GenICam
  backends, and give the same specific error messages.
- Empty entries in `GENICAM_GENTL64_PATH` no longer cause the current
  directory to be searched for producers.

---

## [3.6.9] — 2026-05-04

### Fixed

- **`ROIDemo` recorded the full frame instead of the ROI** — `QCamcorder.__init__`
  unconditionally sets `dvr.source = self.source` after `_connectSignals()`,
  overwriting the `dvr.source = self.roi` assignment that `ROIDemo._connectSignals`
  had just made.  Fixed by overriding `__init__` in `ROIDemo` to reassign
  `dvr.source` after `super().__init__()` completes.
- **`ROIDemo` ROI unresponsive with high-speed cameras** — display rendering
  was unthrottled, letting a 100+ fps camera saturate the GUI thread and starve
  mouse events.  `ROIDemo` now caps display at `DISPLAY_RATE` (default 30 fps)
  via `QVideoScreen.framerate`.
- **`ROIDemo` fixed ROI position/size unsuitable for large sensors** — replaced
  the hardcoded `ROI_POS`/`ROI_SIZE` class constants with `_roiGeometry()`,
  which computes a quarter-area ROI (each dimension halved, rounded down to a
  multiple of 8) centered on the live frame at startup.
- **DVR file-format filter invisible in file dialog on macOS** — `getSaveFileName`
  and `getOpenFileName` were using the macOS native dialog, which only shows a
  format popup when multiple filter groups are present.  Passing
  `DontUseNativeDialog` forces Qt's cross-platform dialog, which always renders
  the supported formats (``*.avi``, ``*.mkv``, ``*.mp4``, ``*.h5``) in a
  visible "Files of type:" combo box.

---

## [3.6.8] — 2026-05-04

### Fixed

- **`fps` alias floods GenICam tree with warnings on startup** — the
  `AcquisitionFrameRate` → `fps` alias added to `_properties` was not
  excluded from `QGenicamCamera.settings`, causing `QGenicamTree._sync`
  to call `set('fps', …)` on every `sigTreeStateChanged` emission (which
  fires once per visible parameter during startup).  Added `'fps'` to
  `_ALIASES` (formerly `_SHAPE_ALIASES`) so the alias is available for
  attribute access (`camera.fps`, `source.fps`) but is never forwarded
  to the tree sync loop.

### Added

- **Quickstart documentation** — new `docs/quickstart.rst` page covering
  installation, the `QCamcorder` CLI, a minimal live-feed example, camera
  controls, and filters.
- **Extending QVideo chapter** — new `docs/extending.rst` covering how to
  write stateless, stateful, and parameterized filters, and how to build
  overlay worker/graphics/widget triplets with composite recording support.

### Changed

- `README.md` — added Graphical overlays to the Features list; added
  Filters and Overlays tables; fixed broken PyPI image URL.
- Corrected British spellings to American English throughout source,
  tests, and documentation (`colour → color`, `normalisation → normalization`,
  etc.).

---

## [3.2.3] — 2026-03-21

### Fixed

- **`QGenicamTree` auto-control updates** — a 500 ms poll timer now refreshes
  all visible GenICam node values from the camera so that autonomous
  camera-side changes (e.g. `GainAuto` reverting from `"Once"` to `"Off"`,
  `Gain` being adjusted during auto-exposure) are reflected in the UI without
  requiring host-side notifications.  `PyNodeCallback` is not used because it
  fires only on host writes, not on camera-internal value changes.
- **`AcquisitionResultingFrameRate` (and similar derived read-only nodes) not
  updating** — `_updateLimits` is now called before the value loop in
  `_pollCamera`, so pyqtgraph's float/int parameter limits are current before
  `setValue` is called.  Previously the stale max bound caused the new value
  to be silently clipped, leaving the display stuck at the old reading.
- **Segfault on exit after adjusting GenICam controls** — three-layer fix:
  (1) `_cleanup()` now nulls `nodeMap` immediately after the harvester is
  reset, so `has_node()` returns `False` for any access after teardown;
  (2) `_pollCamera()` returns early if the camera is no longer open;
  (3) `_pollTimer.stop` is connected to `aboutToQuit`, stopping the timer
  within the same signal dispatch that triggers camera cleanup, eliminating
  the window in which a queued timer event could fire against a freed C++
  genapi object.
- **`QGenicamCamera` startup warnings** (`Unknown property`, `Unsupported
  property`) — `QFlirTree` now filters `_DEFAULT_SETTINGS` to only apply
  keys that are registered on the connected camera, eliminating warnings for
  model-specific nodes absent on a given device.  The `width`/`height`
  lowercase aliases are excluded from `QGenicamCamera.settings` so they are
  never forwarded to the tree.
- **`ExposureTime` read-only after `ExposureAuto="Once"` sweep** —
  `_register_features` now always creates a setter; the setter checks the
  current access mode dynamically at call time so features that are
  temporarily read-only during an auto sweep become writable again once the
  sweep completes, without requiring re-registration.
- **`QGenicamCamera` getter access-mode check** — getters now check the
  current access mode before reading and return `None` for features that are
  not readable at call time, preventing stale reads from nodes whose mode
  changes after acquisition starts.
- **`camera.settings =` interface for GenICam backends** — `Basler`, `IDS`,
  and `MV` trees updated from the removed `setSettings()` call to the
  standard `camera.settings = ...` property assignment.
- **`QCameraTree` column layout** — name column now uses
  `resizeColumnToContents` (more accurate than `sizeHintForColumn + 20`) and
  the value column stretches to fill remaining width.  Tree indentation
  reduced from 20 px to 10 px, significantly narrowing the widget for cameras
  with long property names.
- **`QVideoScreen` aspect ratio** — a `resizeEvent` override and deferred
  `_fitToVideo` slot keep the containing window height consistent with the
  video aspect ratio as the window is resized or the source changes.

### Added

- **`QFlirCamera` Spinnaker 4.3 warning** — docstring `.. warning::` directs
  users to downgrade to Spinnaker 4.1.0.172 if they experience a hang on exit
  caused by a `DevClose()` bug in 4.3.0.189 (confirmed by FLIR support).
- **`FilterDemo`** — `demos/filterdemo.py` refactored: the class is renamed
  from `Demo` to `FilterDemo` and now subclasses `Demo` (DRY).

### Documentation

- Sphinx 8.x duplicate-object description warnings eliminated via a
  `PythonDomain.note_object` patch in `docs/conf.py setup()`.
- `docs/api/dvr.rst` and `docs/api/demos.rst` expanded with per-module
  sections and usage examples.
- Architecture diagram and prose updated to reflect `QVideoScreen`,
  `FilterDemo`, and `ROIDemo`.
- `#:` attribute doc-comments added to all PyQt signals across `lib/` and
  `dvr/` to suppress Sphinx emphasis-in-signature warnings.
- `:doi:` roles converted to plain URL hyperlinks in `filters/Median.py` and
  `filters/MoMedian.py`; footnote labels deduplicated.

---

## [3.2.2] — 2026-03-20

### Changed
- **`QVideo.__version__`** now reads from installed package metadata via
  `importlib.metadata`; `version.py` is deleted.  `pyproject.toml` is
  the single source of truth for the version string.
- **`docs/conf.py`** reads the release version via `importlib.metadata`
  and sets `QT_QPA_PLATFORM=offscreen` for headless autodoc builds.
- **ReadTheDocs** support added (`.readthedocs.yaml`).

### Fixed
- Broken `automodule` directives in `docs/api/cameras.rst` left over
  from the v3.2.0 rename (`QOpenCVResolutionTree`, `QGenicamCamera`,
  `QGenicamTree` → removed; covered by package-level directives).

### Documentation
- Module-level docstrings added to all 14 `lib/` modules.

### Housekeeping
- `__all__` style unified to split-string form across all camera backends.
- `numba` removed from `autodoc_mock_imports` (no longer a dependency).
- `.gitignore`: added `devel/` and `.claude/`.

---

## [3.2.1] — 2026-03-20

### Fixed
- **`numba` removed from required dependencies** — `numba` was listed as a
  core dependency but is only used in an experimental development file
  (`filters/devel/FastMedian.py`) that is not part of the installed package.
  Removing it eliminates an unnecessary ~200 MB download (LLVM) from every
  `pip install QVideo`.

---

## [3.2.0] — 2026-03-19

### Changed
- **Camera module files renamed** — implementation files in each backend are
  now named `_camera.py`, `_tree.py`, and (for OpenCV) `_resolution_tree.py`
  instead of the old `Q<Name>Camera.py` / `Q<Name>Tree.py` names.  This
  eliminates a class/module name collision where importing a backend module
  via its full dotted path caused Python to overwrite the exported class
  reference in the parent package namespace with the module object.

  The **public API is unchanged** — `from QVideo.cameras.X import Q<Name>Camera`
  continues to work exactly as before.  Only code that imported directly from
  the private module path is affected:

  ```python
  # Old (broken):
  from QVideo.cameras.Noise.QNoiseCamera import QNoiseCamera

  # New (correct, and already the documented form):
  from QVideo.cameras.Noise import QNoiseCamera
  ```

### Added
- **`CONTRIBUTING.md`** — developer guide covering environment setup, test
  conventions, backend and filter authoring, and the pull-request workflow.

### Infrastructure
- GitHub Actions workflows opt into Node.js 24 ahead of the June 2026
  forced migration.

---

## [3.1.0] — 2026-03-19

### Added
- **`QPicamera.fps`** — frame-rate property via `FrameDurationLimits`; pinning
  both elements to the same value locks the sensor to a fixed frame rate.
  `read()` now uses `capture_request()` for improved capture efficiency.
- **`QOpenCVResolutionTree`** — new tree widget that replaces the separate
  `width` / `height` spinboxes with a `"W×H"` drop-down populated by probing
  the hardware at startup.  Falls back to spinboxes when only one resolution
  is available.  Accessible via the `-r` flag in `lib/chooser.py`.
- **`QFPSMeter` and `VideoFilter`** added to `lib.__all__`.

### Tests
- Added 48 tests covering `QBaslerCamera`, `QFlirCamera`, `QIDSCamera`, and
  `QMVCamera` / `QMVSource` (12 tests per backend).  Total: 1138 tests.

### Removed
- All `.py~` editor backup files deleted from the repository.

---

## [3.0.0] — 2026-03-18

### Added
- **`QCamera.registerProperty` / `registerMethod`** — unified registration
  system; subclasses call these in `_initialize` to expose camera parameters.
  The base-class `get`, `set`, and `execute` route through the registry,
  holding `self.mutex` for thread safety.
- **`QCamera.__getattr__`** — attribute-style access to registered properties
  (`camera.fps`, `camera.width`) without declaring explicit Python properties.
- **`QCamera.settings` property** — returns all registered property values as
  a `dict`; the setter applies a dict of values via `set`.
- **`QGenicamCamera`** — rewired to `registerProperty` / `registerMethod`:
  walks the GenICam node tree at initialization and registers every accessible
  feature, with stop/restart logic for protected features encoded in setter
  closures.
- **`QFPSMeter`** — rewritten with a sliding-window algorithm for accurate,
  low-latency frame-rate measurement.
- **`resolutions.py`** — cross-platform camera resolution probing replaces
  the previous static lookup table.
- **`QListCVCameras`** — soft OpenCV dependency with probe fallback.
- **`CLAUDE.md`** — developer guide committed to the repository.
- **`cameras/Basler`** — new GenICam backend for Basler cameras via the
  pylon GenTL producer (`ProducerU3V.cti` / `ProducerGEV.cti`).
- **`cameras/IDS`** — new GenICam backend for IDS Imaging cameras.
- **`cameras/MV`** — new GenICam backend using the MATRIX VISION
  mvGenTLProducer for broad camera compatibility.
- **`QGenicamCamera._findProducer`** — static method that searches
  `GENICAM_GENTL64_PATH` (set by all GenICam SDK installers) for a
  named `.cti` producer file; replaces bundled producer directories.
- **`QGenicamTree._updateValues`** — refreshes read-only GenICam node
  values in the property tree after any property change.
- **`QPicamera`** — rewritten: `cameraID`, `width`, `height` parameters;
  `_probeControls` registers all supported picamera2 controls (exposure,
  gain, brightness, contrast, etc.) with hardware-reported ranges.
- **`QPicameraSource`**, **`QPicameraTree`** — new classes following the
  standard camera backend pattern.
- **Sphinx documentation** — full API docs with autodoc, napoleon,
  intersphinx, and furo theme.
- **`demos/`** — module docstrings; all demos use `choose_camera` for
  consistent camera selection.
- Full test suite: **1050+ tests**, 0 failures, covering all core modules,
  camera backends, filters, DVR, and utilities.

### Changed
- `QCamera._properties` and `._methods` are now dicts (keyed by name) rather
  than lists; `QCameraTree` reads them to auto-build the property tree.
- `QCamera.properties`, `.methods`, and `.settings` are now `@property`
  descriptors; previously some backends shadowed them as plain methods.
- `QGenicamCamera`: removed bespoke `set`, `get`, `execute` overrides;
  removed explicit `width`, `height`, `fps` Python properties; removed
  `__properties`, `__methods`, `__modes` static helpers.  `IString` is now
  registered alongside the other property types.
- `QGenicamCamera.protected` is now a `set` (was a `list`).
- `QOpenCVCamera`: device properties probed at runtime and registered only
  if the hardware supports them.
- `QListCameras`: enforced override contract; fixed signal guard.
- `QCameraTree`: improved coverage; fixed pyqtgraph `DeprecationWarning`.
- `QDVRWidget`: fixed writer close bug, disconnect safety; added `newFrame`
  signal.
- DVR subsystem: consolidated readers/writers; added HDF5 and OpenCV formats.
- `QFilterBank`: fixed `deregister`; improved docstrings and test coverage.
- `chooser.py`: data-driven dispatch, full docstrings and tests.
- `clickable`: PyQt5/PyQt6 compatibility fix.
- Packaging: switched to `setuptools.build_meta`; added explicit
  `package-dir` map; added optional-dependency groups (`genicam`,
  `picamera`, `dev`).

### Removed
- `cameras/Genicam/nodemap.py` — dead code; logic moved into
  `QGenicamCamera` private static methods (now also removed in favor of
  `registerProperty`).
- Exploratory Jupyter notebooks from `cameras/Genicam/` and
  `cameras/Spinnaker/`.
- `lib/QCameraList.py` — superseded by `QListCameras`.
- `cameras/Spinnaker` and `cameras/Spinnaker2` — retired from the released
  package; FLIR cameras are now supported via the GenICam interface
  (`cameras/Flir`).  The Spinnaker backends are preserved in `devel/` for
  reference.

### Fixed
- `QGenicamCamera._initialize`: removed `try/finally` anti-pattern that
  silently swallowed the `self.name` `AttributeError` and left `protected`,
  `_properties`, and `_methods` uninitialized.
- `QGenicamCamera`: `IProperty` union type now defined inside the
  `try` block, preventing `NameError` when `genicam` is not installed.
- `QGenicamSource.__init__`: no longer forwards `*args` to
  `QVideoSource.__init__`.
- `QVideoSource`: fixed frame-rate reporting and thread-safety edge cases.

---

## [2.1.0] and earlier

Initial development at New York University.  Camera backends for OpenCV,
GenICam (Harvesters), FLIR/Spinnaker, and Raspberry Pi.  Core display,
DVR, and filter subsystems.
