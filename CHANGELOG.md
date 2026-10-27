# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [4.7.2] — unreleased

### Added

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
- **Color recordings to `.avi` and `.mkv` use HuffYUV, gray ones FFV1.**
  Both are lossless, and HuffYUV encodes color frames several times faster,
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
  `_properties`, and `_methods` uninitialised.
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
