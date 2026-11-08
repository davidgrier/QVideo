# QVideo — Future Work

Ideas for upgrades and extensions, in no particular order.

---

## Polish after the review of 2026-11-03

The review of 2026-11-03 kept to what the CI then checked (`ruff` with
pyflakes, bugbear and the line length).  A stricter pass (`ruff --isolated --select
E,W,F,B,SIM,C4,C901,PIE,RET,UP,PERF,PLR,RUF,PLW`) finds these; fix them
together.  CI now enforces `SIM` (but `SIM905`), `PERF`, `PIE`, `RUF012`,
`PLW2901` and `UP037` for the package, not for the tests:

- [x] Done 2026-11-04: `contextlib.suppress`, constants as tuples or
      `ClassVar`, overwritten loop variables, `.get(x, None)`, `None` last
      in a union, quoted annotations that did not need quotes, the
      docstrings that no base class supplies (what is left is `to_code`
      and `run` overrides, which inherit theirs).  The `lambda: saver.wait()`
      in `dvr/QCircularDVRWidget.py` stays: `destroyed` passes the object,
      which `wait` must not receive.
- [x] Decided 2026-11-06, no change: wide signatures (`QRemoteCamera`,
      `QOpenCVCamera`, `QPicamera`, the trackpy overlay).  Every argument is
      a keyword-only option that stands alone; a config object would add a
      layer and lengthen the call sites.
- [x] Decided 2026-11-06, no change: `QVideoWriter.framenumber` stays.  It
      is documented public API on the writer, the readers, `QPlayer` and
      `QDVRWidget`, and it is a count, where the signal `frameNumber` is an
      event.  A rename would be breaking for little gain.
- [x] Decided 2026-11-06, no change: the snake_case public parameters of
      filters (`sigma_s`, `block_size`, `low_sigma` and so on) are
      constructor keywords with the names of OpenCV and the literature.
      `CLAUDE.md` says so now; it had said that `VideoFilter` is not a Qt
      class, which it is.

Things noticed, not changed:

- [x] Done 2026-11-06: `interactive.live_view` reads and encodes each frame
      in a worker thread (`asyncio.to_thread`), so the kernel no longer waits
      for the camera.
- [x] The Genicam and Viva cameras repeat the alias tables, the USB speed
      check and the registration of aliases.  Decided 2026-11-04 to leave it:
      they are complementary backends, and one may be dropped.

---

## An image saver for `QSnapshot` and for applications  **Built 2026-11-07**

`QSnapshot._save` turns an array into a file, but only for frames that it
caches from a signal, only in the home directory, and it only logs a failure.
Other applications that import QVideo (QHOT saves the video and the pattern
on its SLM) pull an image on demand and want every outcome in the status bar.
The saver takes the image as an argument, so any array can be saved.

- [x] **`imageops.save_image(image, filename, levels=None)`**: the array to
  file step, with no widgets.  `(H, W)`, `(H, W, 3)` and `(H, W, 4)` arrays of
  `uint8` become a `QImage` (the format follows the extension), and `uint16`
  gray is saved as it is now by `QSnapshot` (16 bit PNG or TIFF, stretched by
  `levels`).  It raises and does not log: `ValueError` for a dtype or shape
  that cannot be saved, `OSError` if the file cannot be written.
- [x] **`QImageSaver`** (`lib/`, a `QObject`): `save(image, filename=None,
  ask=False) -> str | None` returns the path, or `None` if the user cancelled.
  - A filename is used as given.  Without one the name is
    `<prefix>_YYYYMMDD_HHMMSS.png` in `directory`, and an existing file is
    never overwritten (a suffix is added).
  - `ask=True` opens the save dialog, with that timestamped name as the
    default.
  - `message(str)` reports each outcome ("Saved ...", "Could not save ...:
    reason"), so that the status bar of a `QCamcorder` or `QMainWindow` shows
    it.
- [x] **`QSnapshot` uses it** and keeps what is its own: the cache and the
  shortcuts (`snap` calls `save`, `snapAs` calls `save(ask=True)`).
  `QCamcorder` connects `message` to its own.  This settles the `uint16`
  question in one place.
- Test: the pixels read back from the file equal the array, for gray, RGB and
  RGBA; an array that is not contiguous; a path that cannot be written; the
  default name, the suffix when it exists, the cancelled dialog, and the
  message of each outcome.

---

## The tree shows what the camera did on its own  **Done for Viva 2026-11-08**

`QCameraTree` read the camera back only after a change made in the tree, so
a camera that changes by itself was not followed: `ExposureAuto = Once`
resets to `Off` within a second but the tree kept showing `Once` (and
choosing `Once` again did nothing), and the exposure time and gain after an
automatic sweep were the old ones.

The first idea was a timer in the tree.  The better one (David's) is to ask
the camera: viva-genicam tracks the invalidator map (`changed_since` after a
write) and the `PollingTime` that the XML declares for features that change
by themselves (`poll()` names those that are due).  Measured on the
Blackfly S (`devel/vivaprobe.py`): `ExposureAuto`, `ExposureTime`,
`GainAuto` and `AcquisitionResultingFrameRate` declare 0.5 s, and a read
returns the camera's value only after that time.

- [x] `QCamera.watch(names)`, `_changes()` (called by `saferead` after each
  frame, holding the lock) and the signal `propertiesChanged(dict)`.
- [x] `QVivaCamera._changes`: asks only when something can change (a write
  that touches a watched feature, directly or through `changed_since`, or an
  `...Auto` mode that is not `Off`); then `poll()` twice a second, the
  watched features that are due, one hold of the camera, only values that
  differ; it looks again at what is writable; it stops after two polls
  without news and no automatic mode on.
- [x] `QCameraTree` watches what it shows, applies the signal without
  sending it back, and reads its properties with `QCamera.snapshot` (one
  hold) after an edit.
- [x] **On the camera** (`devel/vivafollow.py`, 2026-11-08): with the
  signal, the tree shows `Off` and 14998 µs, writable, half a second after
  `Once`; without it the tree stays at `Once` and 2001 µs.  The frame rate
  is the same (67.8 against 68.0 a second while settling, 66.2 against 66.0
  idle).  `devel/vivaidle.py` counts the polls: none idle, 2 or 3 after a
  write, 2 a second under `Continuous`, none again after `Off`.
- [ ] Use the invalidator map after the user's own writes
  (`changed_since`): the tree reads back all that it shows, which one
  snapshot makes cheap; the map would name only the dependents.  Not needed
  yet.
- [x] **Genicam (Harvesters)** (2026-11-08): `QGenicamCamera._changes`
  with the same arm, poll, quiet rule as Viva, `NodeMap.poll(ms)` in place
  of `changed_since` (the binding reports neither `polling_time`, which is
  -1 for every node, nor which nodes are due, so it reads every watched
  node and ignores counters and temperatures when it decides whether
  anything is going on); a `changes` event from the worker, re-emitted by
  `QRemoteCamera`; the 200 ms GUI-thread poll and the worker's push are
  gone.  Checked on the Blackfly S through the worker
  (`devel/genicamfollow.py`).  Without `NodeMap.poll`, `ExposureAuto`
  stays `Once` for ever, so the Genicam tree did have the bug in a
  weaker form (it went stale until something else moved).
- [ ] Genicam: read only what is due.  With `polling_time` at -1 the
  binding gives no list; the XML has `PollingTime` on private nodes
  (`ExposureTime_FloatVal`) and `pInvalidator`/`pDependent` link them to
  the features: walking that graph would cut the 15 to 35 ms that a read
  of every shown node costs, twice a second while armed.
- [ ] Share the arm, quiet and automatic-mode policy of Viva and Genicam in
  a helper (two real users now).

---

## Limit the work of the filter pipeline  **Idea; not sure how**

The pipeline runs its filters on every frame that the camera delivers, even
when the screen can show fewer.  Measured with the Noise camera (500 fps,
248 delivered), a trivial filter and an offscreen screen that shows 81 a
second: 67 % of the filter calls were never shown; at 116 delivered, 30 %.
With a blur in OpenCV the whole process used 291 % of a CPU and, with 30
frames a second let through, 109 %.  The display was not jerky without a
limit (the gaps between displayed frames had a standard deviation of 1 to
2 ms), and the heartbeat of the GUI did not improve with one.  A limiter
that picked frames by arrival time inside the worker made the cadence
worse (4 to 7 ms).  So the gain is CPU, heat and the GIL, not speed: with
`depth=1` a saturated pipeline already takes the newest frame, and its
output rate is one over the time per frame.

**Measured on a camera, 2026-11-04** (Flir Blackfly S, 1280x1024 Mono8, the
chain of `QCamcorder -f`; frames counted by a slot in the GUI thread, six
seconds a stage, two runs).  At 66 frames a second, a dark scene, nothing
could be told from the noise (the same configuration varied by 6).  At about
145 frames a second, a lit scene, the chain loses frames and the loss
repeats:

| Stage | Run 1 | Run 2 |
|-------|-------|-------|
| source only | 144.7 | 147.2 |
| source and display | 129.2 | 135.7 |
| tree, polling | 125.7 | 127.5 |
| tree, polling stopped | 135.7 | 136.3 |
| tree and display | 110.8 | 114.3 |

The display costs 8 to 10 %, the polling of the tree 7 %, and a tree with
the polling stopped another 7 % that nothing explains yet.  The program
receives fewer frames, so this is more than a lower displayed rate.
`QVideoScreen(framerate=30)` gave back the cost of the display (144 against
133 frames a second); `framerate=60` did not measurably (135), and with the
tree present neither helped (114).  The scatter between runs is about 5.
Watching 201 nodes instead of the 17 of the Flir tree cost 11 % at 66
frames a second, and 40 nodes 1.5 %, so the cost is not simply the number of
nodes.  The window of `QCamcorder` alone was too noisy to use (120 and 138).

- [ ] Find where the other 7 % goes when a tree exists and nothing polls:
      the settings that `QFlirTree` applies to the camera, the widget, or
      the capture thread's competition for the interpreter lock.
- [ ] Measure again with a steady scene and a fixed exposure, so that the
      camera's own rate does not move, and with more runs.

- [ ] Find out whether the display gets smoother, which has not been
      tested: (1) filters about as slow as the camera period, where the
      pipeline picks frames unevenly in capture time; (2) a filter in pure
      Python in a busy application such as QHOT, where the pipeline thread
      competes with the GUI for the interpreter lock.
- [ ] A recorder that takes the filtered stream needs every frame, and a
      limit would cut its rate; the file would also declare the rate of the
      camera and play too fast.  So the limit must be off while such a
      recording runs, and `fps` of the pipeline must follow the limit.
- [ ] The mechanism, if it is built.  Passing every Nth frame by
      `FrameInfo.index`, as `nskip` does for the recorder, is exact and needs
      no clock.  Other candidates: a `maxFps` on the pipeline checked where
      frames arrive; a filter that returns `None` (the pipeline drops such
      frames, but a filter cannot change `fps`); consumers that say what rate
      they need.  The limit of the pipeline and `framerate` of the screen
      should be equal, or only one of them set, so that they do not beat.

---

## Capture that does not freeze the process (GenICam and the interpreter lock)  **Resolved 2026-11-06**

**Resolved 2026-11-06** for both the official GenICam stack (Harvesters)
and viva-genicam: capture no longer freezes the GUI.  The text below is the
record of the problem and of how it was approached.  Its unchecked items
were written before the resolution; review each one and delete it, or keep
it as a separate item, the next time this file is tidied.

The `genicam` binding that harvesters uses holds the Python
interpreter lock while it waits for a frame and while it reads nodes, so a
streaming Flir camera freezes every other thread of the process: in QHOT the
traps respond with a median wait of 28 ms and 3 holograms a second, against
5 ms and 10 a second with OpenCV.  The evidence, the upstream issue
(genicam/harvesters #508) and what was ruled out are in
`docs/compatibility.rst` (Known issues); the programs that measured it are in
`devel/genicam_gil/`.  PySpin releases the lock, and has no such problem.

The aim: wait for the next frame without holding anything that the rest of
the program needs, so that a program can calculate and project holograms,
and draw, while it waits.  Two ways, which do not exclude each other:

1. **Capture in a separate process** (`QRemoteCamera`).  The camera and its
   vendor library run in a child process with a lock of their own; the
   parent has a `QCamera` proxy whose `read()` waits on an operating-system
   semaphore, which releases the lock.  Frames travel in a ring of
   `multiprocessing.shared_memory` slots (1280 x 1024 at 67 fps is 88 MB/s,
   one copy in and one out); commands (`get`, `set`, `execute`, `settings`,
   `states`, a `describe()` of the node tree) go over a pipe.  The rest of
   QVideo (the source thread, `QFrameRelay`, the DVR, the filters, the
   trees) is unchanged, because it sees a `QCamera`.  It fixes every GenICam
   backend, not only Flir, and **the worker may run another Python than the
   program**: the Spinnaker SDK ships PySpin for CPython 3.8, 3.9, 3.10 and
   3.12 only, and pins `numpy<2`, which a program on 3.13 or 3.14 cannot
   use in-process.
2. **A Flir backend on PySpin** (`QSpinnakerCamera`).  PySpin was measured to
   release the lock (a counter in the main thread ran at 100 % while another
   thread waited in `GetNextImage`; an unrelated thread woke in 0.061 ms,
   idle 0.063 ms) and `GetNDArray()` costs 0.46 ms a frame.  The least code,
   but it needs Python 3.12 or older and NumPy 1.x in the program, it serves
   Flir cameras only, and the tree, which reads GenApi nodes, has to be ported
   to PySpin's nodes.  Whether the node reads (the tree's poll) also release
   the lock has not been measured.

Plan, with a gate before each large step:

- [x] **Spike, throwaway, about half a day** (done; **the gate passed on the
      Flir on 2026-11-02**, see the table below): a child process that runs harvesters and writes frames to shared
      memory, and a stand-in camera in the parent that reads them; measure
      in QHOT with the Flir (`QHOT/devel/flirdiag.py`, local).  **Gate**:
      with traps being added, event-loop median <= about 7 ms (OpenCV: 5.2),
      99th percentile <= about 25 ms (OpenCV: 12.7), holograms >= 9 a second
      (OpenCV: 9.8), frames >= 24 a second.  If it fails, stop: the lock is
      not the only cause, and the fallback is below.  *Result so far*: with
      a stand-in that holds the lock the way the binding does
      (`ctypes.PyDLL`, `QHOT/devel/gilcamera.py`) the 99th percentile stays
      at 6 ms with the camera in a worker, against 21 to 36 ms in the
      process, and frames and holograms do not change; the stand-in is milder
      than the Flir (median 5.7 ms against 28 ms).

      *Result with the Flir* (Blackfly S, 30 frames a second, `traps` mode of
      `QHOT/devel/flirdiag.py`, median of 3 trials; the remote run uses the
      real `QGenicamTree` through `make_tree`, as `qhot -f` does now):

      | | frames/s | loop med ms | loop p99 ms | loop max ms | holo/s | cpu % |
      |---|---|---|---|---|---|---|
      | local, no stopgap | 17.8 | 23.5 | 70.2 | 123.8 | 5.2 | 68 |
      | local, `swi0.5` (what QHOT ships) | 26.9 | 6.0 | 26.3 | 33.6 | 9.8 | 68 |
      | **remote (`QRemoteCamera`)** | **30.1** | **4.6** | **8.2** | **10.2** | **9.9** | **43** |

      The remote camera meets the gate without the switch-interval stopgap,
      and beats OpenCV's figures above.  Interactive use of `qhot -fr` (the
      `-r` is gone now) was
      smooth at 170 Hz and at 5 Hz.
- [ ] Audit what touches a camera: the trees (`QCameraTree`, `QGenicamTree`
      call `settings`, `set`, `node`, `hasNode`, `states`, `properties`,
      `name`, `model_name`, `isOpen`), the DVR, the sources, the filters.
- [x] `QRemoteCamera`, the worker, the protocol, the ring; lifecycle: start,
      clean shutdown, death of the parent (the child exits and unlinks the
      shared memory), crash of the child (`read()` fails, the source says so).
- [ ] `describe()`: the node tree as plain data, for `QGenicamTree`, which now
      calls `camera.node('Root')` and `camera.node(name)`, objects that cannot
      cross a process.
- [x] A change of shape (region of interest, binning) reallocates the ring,
      with a handshake (a generation number in every announcement).  How the
      change is announced is below.
- [x] Tests with the noise camera through the remote path, so that CI needs
      no hardware: `tests/test_qremotecamera.py` (shape change, shutdown,
      crash, orphan cleanup, reopening) and `tests/test_conformance_remote.py`
      (the whole contract of `tests/conformance.py`).
- [x] Verify with the Flir (done, above).  [ ] Release QVideo; QHOT needs
      only the new QVideo requirement, and can then drop `SWITCH_INTERVAL`
      for a camera that runs in a worker.

Before `QRemoteCamera` can be the default (see "Defaults" below); each of
these is a reason not to make it the default today:

- [~] **A tree that does not block the interface** (the polling is done:
      the worker pushes the states; settings still wait for the frame).  Original item:  A request is a round
      trip, and `QGenicamTree._pollCamera` asks for `states()` five times a
      second, which takes 17 to 18 ms in the worker: the GUI thread would wait
      for that, which is a stall of the event loop even though it is not a
      lock.  The worker should read the states between frames and push them,
      and the GUI should read the latest push.  Make every setting that the
      interface sends asynchronous, or at least off the GUI thread, and say
      what happens when the worker is in a long read (a setting waits for the
      read: up to a frame period, a second at one frame a second).
- [ ] **What the trees need**: `node`, `hasNode`, `states`
      (`describe()` above) and any other call that a backend's tree makes
      beyond the registry of properties.  Audit `tests/test_vendor_trees.py`
      and the tree of every backend.  Only plain values cross the process: a
      backend that hands out callbacks or native objects needs a reply of
      plain data.
- [x] **Announce a change of shape from the worker**: done.  The worker
      compares the shape of each frame with the last one that it announced
      and sends a `shape` event ahead of the first frame of a new shape.
      `tests/test_qremotecamera.py::TestTheCameraChangesTheShape`.
- [ ] **Windows.**  There is no file descriptor to pass to a child.  Use
      `multiprocessing.connection` (named pipes), shared memory by name, and
      a second connection in place of the datagrams, so that the same code
      runs on every platform; then remove the skips of the tests and the
      error that `QRemoteCamera` raises.
- [ ] **macOS camera permission** for a worker that a packaged application
      starts: the permission belongs to the application that is responsible
      for the process.  Try it from an application bundle; if it fails, say
      what to do.  (From a terminal it works.)
- [ ] **Errors and debugging.**  Forward the logging of the worker to the
      logging of the program, with the traceback of an exception as text, and
      keep a way to run the very same camera in the program for a debugger
      (done: create the class, `QFlirCamera()`).  Say in the interface when
      the worker has died, not only in the log.
- [ ] **What it costs**, measured and written down: the start of the worker
      (3.7 s for OpenCV), the copy of a frame in and out of the ring, the
      latency of a frame and of a setting, and the highest rate at the largest
      frame (a 6 MB color frame at 30 frames a second is cheap; a fast
      camera at its full resolution may not be).
- [x] **Defaults** (2026-11-03).  The `worker` field of each entry in
      `BACKENDS` says whether a backend opens in a worker: the Harvesters
      backends (Flir, Basler, IDS, MV, VimbaX) on macOS and Linux, the rest
      in the program.  There is no `-r` and no `--local`; creating the class
      (`QFlirCamera()`) keeps a camera in the program.  QHOT dropped its
      stopgap (`SWITCH_INTERVAL`, `readsGenicam`, `shareTheInterpreter`);
      it needs the QVideo release that has this.  [ ] Say in the interface
      which one a camera got (for example `QFlirCamera (own process)` in the
      title of the tree).  [ ] Windows.
- [ ] **Unknown options.**  `launch` reads the command line with
      `parse_known_args`, so a flag that it does not know (a stale `-r`, or
      a typo such as `-cx`) is ignored without a word, and a program then
      runs a camera that the user did not ask for.  Stop on an option that
      no part of the program claims, or at least warn.

- [x] **Decision, 2026-11-03: the worker is for Harvesters only.**  Viva is
      the preferred GenICam interface (documented), so the worker is
      automatic for the backends built on `QGenicamCamera` and `-r` is
      gone.  The class stays generic, because the tests send the noise
      camera through it.  Windows has no worker, so the Harvesters backends
      stay in the program there and keep the defect.
- [ ] **Retire the Harvesters backends that nobody has tested?**  Flir has
      run on hardware; Basler, IDS, MV and VimbaX have not (see
      `docs/compatibility.rst`).  Each is about 60 lines on top of
      `QGenicamCamera`, which stays: it is the standard implementation and
      Flir needs it.  Keeping them costs little; removing them strands
      anyone whose camera needs a producer for a transport that Viva does
      not speak.  Suggested path: wait until Viva has run on a camera of
      another maker; mark the four as unverified in the help and the
      documentation; warn when one is instantiated for one minor release;
      remove them in the next major version if nobody has reported use.

Cheaper, and worth doing whatever else is decided:

- [x] `QGenicamTree._pollCamera`: removed (2026-11-08); see the change
      reporting above.
- [ ] Add what we know to genicam/harvesters #508 (see
      `docs/compatibility.rst`): that `_gentl.so` and `_genapi.so` import no
      `PyEval_SaveThread`, that a longer wait is worse, and that the node
      reads are affected too.

Fallback if the spike fails: `sys.setswitchinterval(0.0005)` in the program
took the Flir in QHOT to a median wait of 5.9 ms and 9.7 holograms a second
(measured, 3 trials), and with the camera poll stopped, a 99th percentile of
26 ms; it treats the symptom, and affects the whole process.

*Care with the camera*: its frame rate (`AcquisitionFrameRate`,
`AcquisitionFrameRateEnable`) is kept by the device after the program ends,
so a measurement that changes it must put it back.  The programs in
`devel/genicam_gil/` change nothing but the wait slice of harvesters, and
put it back.

## Review the documentation of the camera in a process of its own

Do this before the first release that has `QRemoteCamera`, and again when it
becomes a default.

- [ ] **Docstrings.**  Every public class, method and property of
      `lib/remote/camera.py` has a NumPy-style docstring that says what the
      caller needs and nothing of the implementation; the private modules
      `lib/remote/protocol.py` and `lib/remote/worker.py` say what each function
      does.  Run the docstrings through the documentation build and read the
      pages, not only the source.
- [ ] **The protocol, in one place.**  Describe it once, in the docstring of
      `lib/remote/protocol.py` or in `docs/architecture.rst`: the two channels, the
      layout of the ring and of an announcement, the requests and their
      answers, the life of the worker (start, close, death of the parent,
      death of the worker), what is guaranteed about frames and what is not.
      A person who writes a backend or fixes a bug should not have to read the
      code to learn it.
- [ ] **Check every claim against what the code does**: the platforms, "any
      backend", the numbers of the measurements, the statement in
      `docs/compatibility.rst` that it avoids the lock of the `genicam`
      binding (true only when measured with the Flir), and the text of
      `docs/architecture.rst`.  Anything that has not been measured says so.
      One behavior to state plainly: the proxy delivers the newest frame and
      discards the rest if it falls behind, where an in-process camera hands
      over the frames of its driver's queue, late.
- [ ] **A page for the person who chooses**: when to run a camera in a
      process of its own and when not (what it fixes, what it costs, what it
      cannot do), how (`QRemoteCamera('flir')`), a short example, and what to
      do when the worker does not start.
- [ ] **The older documentation**: `QVideoSource` is called the standard way
      to drive a camera, the quickstart, the READMEs of `lib/`, `cameras/` and
      `tests/`, and the flag lists in `QCamcorder.py` and `demos/__init__.py`
      should agree with the new framework, and `CLAUDE.md` should say how a
      backend's tree and camera are kept compatible with it.
- [ ] **The documentation builds without a warning**, the examples in the
      docstrings run, and a reader who has never seen the code can follow the
      page from the start.  Ask someone who does not know QVideo to try it.


## Resolution and Region of Interest

Camera resolution changes are a common pain point, especially for
scientific cameras that support a large range of sensor modes.

- **ROI selection GUI** — interactive rectangle drawn on the live
  `QVideoScreen` that the user drags to the desired region; a
  "Set ROI" action crops the sensor (or the downstream frame) to
  match.  Cameras that support hardware ROI (width/height/offsetX/offsetY
  via GenICam `OffsetX`/`OffsetY`/`Width`/`Height`) would apply the crop
  in firmware; others would crop in software.
- **Resolution selector for scientific cameras** — `QOpenCVResolutionTree`
  already probes and lists supported resolutions for OpenCV cameras.
  Extend the concept to GenICam backends: enumerate valid
  `Width`×`Height` combinations at initialization and present them as a
  drop-down (or a grouped tree node) rather than exposing raw integer
  spinboxes.
- **Binning and decimation controls** — many scientific cameras expose
  `BinningHorizontal`/`BinningVertical` GenICam nodes.  Detect and
  register these automatically in `QGenicamCamera` so they appear in
  the tree and interact correctly with the ROI spinboxes.
- **Resolution presets** — common aspect-ratio presets (full sensor,
  half, quarter, 1:1 crop, user-defined) accessible from a single
  drop-down to streamline switching during an experiment.
- **Linked width/height spinboxes** — when the camera requires width and
  height to change together (e.g. square ROI for FFT), enforce the
  constraint in the tree widget rather than silently clamping values.

---

## Help a user choose settings for speed  **Idea; thinking**

Raising the frame rate of a GenICam camera is bewildering to a newcomer.
The controls interact (exposure limits the frame period, the interface
limits the throughput, binning and decimation change what ROI means, bit
depth changes the rate), and the ways to the same speed differ in what they
cost: field of view (ROI), resolution (binning, decimation), noise (gain,
short exposure) and contrast.  Most users want to record faster at the
quality they have now.  Some concessions can be predicted before anything
is changed; some can be mitigated, but only by the user (more light allows
less gain at a shorter exposure).  An optimum depends on the instrument.

**Prior art, searched 2026-11-05.**  Nothing found gives advice on the
trade-off; what exists is below.

- *Calculators.*  Basler has an online Frame Rate Calculator (the user
  gives a model and an ROI; it returns the maximum rate), documents that
  height governs the rate on most cameras and width on some, and says to set
  binning before the ROI on some models.  A camera reports its own answer
  in `ResultingFrameRate` (`ResultingFrameRateAbs` on GigE).  Teledyne FLIR
  publishes a table of rates per model, width, height, bit depth, and
  sensor or ISP binning (`softwareservices.flir.com/<model>/latest/Model/
  spec.html`), measured with `DeviceLinkThroughputLimit` at its maximum
  and `AcquisitionFrameRate` disabled.  Hamamatsu explains in prose that an
  sCMOS rate depends on the number of lines, not the width, that sCMOS
  binning is digital and does not raise the rate (it does on CCDs), and that
  the sub-array must be centered on the sensor.  I found no Hamamatsu
  calculator (I had assumed there was one).
- *Presets.*  Andor's OptAcquire (iXon) picks readout speed, vertical clock
  speed and preamp gain for a named purpose: Fastest Frame Rate, Time
  Lapse, Highest Dynamic Range, Photon Counting.  It is the closest thing
  to guidance, but the combinations are fixed by the vendor, do not include
  ROI or illumination, and do not adapt to a stated goal.
- *Viewers* (pylon Viewer, SpinView, Vimba Viewer, IDS peak Cockpit) show
  the rate and the bandwidth in use.  *Micro-Manager*, MATLAB's Image
  Acquisition Toolbox and OpenCV expose the properties and nothing more.
- *Language models on instruments.*  TEM Agent (arXiv 2511.08819) exposes
  the microscope to a model through MCP tools, limited to predefined
  actions, which protects the instrument; the authors found that words such
  as tilt and rotation were read inconsistently across parameters, and that
  a little domain knowledge in the prompt cured it.  A zero-shot
  microscope for 2D materials (arXiv 2504.10281) calls the Zeiss software
  through function schemas.  A patent describes a model that chooses
  settings from a wish and repeats with feedback.  None is about a camera's
  speed and noise.

**What QVideo could add that a vendor tool cannot:** it reads back what the
camera did and can measure the outcome from a few frames: the achieved rate,
the mean level and saturation, the noise (standard deviation of a still
region, or of the difference of two frames).  Each option can then carry
measured concessions, not guesses: "400 fps, field of view 25 %, noise
+30 %, mean level 60 % of full scale".

Two layers, the first needs no model:

1. **A deterministic explorer** for a stated goal ("at least 500 fps",
   "keep the full field of view", "keep the noise"): it knows which nodes
   exist (`Height`, `Width`, binning and decimation selectors, `PixelFormat`,
   `ExposureTime`, `Gain`, the throughput limit, `AcquisitionFrameRate*`),
   tries combinations in a safe order, reads `ResultingFrameRate` after each,
   measures the image, and returns a table of options and their concessions.
   Even this alone ("Fast" with an explanation) would help a newcomer.
2. **A language model that chooses and explains.**  It sees the table and
   the user's goal, asks what the user can change (light, field of view),
   proposes, and calls `set()` through a short list of tools after the user
   approves.  Never a change that the user has not seen; read back what the
   camera did and report the difference.  The SDK is an optional extra, the
   network and a key may be missing in the lab, and no frame leaves the
   machine (only property names, limits and measured numbers).

- [ ] Try layer 1 by hand on the Blackfly S: the rate against `Height`,
  `Width`, binning, bit depth and exposure, with `ResultingFrameRate`, to
  see how much of a table is the same for every camera.
- [ ] Decide where it lives: a recipe in `demos/`, not the framework.
- [ ] A measure of image quality that a few frames can give, and how far
  it can be trusted (noise from a frame difference; saturation fraction).
- [ ] Ask collaborators with other cameras which compromises they make.

---

## New Camera Backends

QVideo currently supports OpenCV, GenICam (Basler, FLIR, IDS, MATRIX VISION,
Allied Vision VimbaX), and Raspberry Pi cameras.  Requested and candidate
additions:

- **Hamamatsu** — at least one user has requested Hamamatsu support.
  Hamamatsu cameras are controlled via the `DCAM-API` SDK, wrapped in
  Python by the [`dcamapi4-py`](https://github.com/nstone8/dcamapi4-py)
  or [`pyDCAM`](https://github.com/HamamatsuPhotonics/pyDCAM) packages.
  Implement `QHamamatsuCamera` / `QHamamatsuSource` / `QHamamatsuTree`
  following the standard backend pattern.  DCAM-API exposes properties
  through an integer-keyed property map; `registerProperty` calls
  would enumerate the readable/writable subset at initialization.
- **Andor (SDK3)** — widely used sCMOS and EMCCD cameras in
  single-molecule and fluorescence microscopy labs.  Andor's SDK3
  Python bindings (`pyandor` / `atcore`) follow a similar property-map
  pattern to DCAM-API.
- **Thorlabs (Zelux / Kiralux)** — Thorlabs scientific CMOS cameras
  are controlled via the `thorlabs_tsi_sdk` Python package.
- **PCO** — PCO cameras use the `pco` Python package, which wraps
  the PCO SDK and exposes properties as a dict-like interface.
- **Azure Kinect / Intel RealSense** — depth + color cameras useful
  for 3-D tracking experiments; would add a `depth` frame type
  alongside the existing `Image` type alias.
- **Aravis** — [Aravis](https://github.com/AravisProject/aravis) (LGPL-2.1)
  is an open-source C library for GigE Vision and USB3 Vision cameras.
  Version 0.9.0 (May 2025) introduced an experimental GenTL producer
  `.cti`; the stable 0.8.x series does not yet include it.  Once the
  0.9.x GenTL producer stabilizes, add a `cameras/Aravis` backend (or
  extend `_findProducer` to locate the Aravis `.cti`) to give users a
  fully open-source, zero-cost path to GigE and USB3 cameras without
  a vendor SDK.  The Aravis simulated camera is also a candidate for
  use in CI tests as an alternative to the existing `cameras/Noise`
  reference implementation.
- **GenICam catch-all** — any camera shipping with a GenTL producer
  `.cti` file can already be used via `cameras/MV`.  Improve
  `_findProducer` to search additional standard paths
  (`GENICAM_GENTL32_PATH`, vendor-specific environment variables)
  and document the generic GenICam entry point more prominently.

---

## One place that knows the types of GenICam nodes  **Done for the camera**

Done 2026-11-04 in `cameras/Genicam/_camera.py`: `_nodeKind` classifies a
node once and `_limits` says what bounds it; the properties, the plain-data
description and the snapshots are built on them.  The disagreements listed
here are gone, except that a snapshot still calls a boolean or a string
`'other'`, because the tree depends on that.

- [ ] `Genicam/_tree.py` and the `_KINDS` table of `cameras/Viva` hold the
  same knowledge again.  They stay separate (the backends are
  complementary); do it for the Genicam tree only if a node type is added.

---

## Video deeper than 8 bits (12 bit and up)

`python qhot.py -g` (viva-genicam) starts fast and runs well, and it is
not tied to Mono8 the way our other GenICam path is.  A scientific camera
usually has Mono10, Mono12 and Mono16 as well.  Everything was tested with
Mono8 only until 2026-11-04; the first item below was then measured, and the
rest has not been checked.

**Measured on a camera, 2026-11-04** (Flir Blackfly S, 12 bit ADC, a lit
scene; `viva` and `QGenicamCamera` through the worker agree):

| Format | dtype | max | meaning |
|--------|-------|-----|---------|
| Mono8 | uint8 | 255 | the top 8 bits of the 12 |
| Mono10p, Mono10Packed | uint16 | 1023 | 10 bit counts, right-justified |
| Mono12p, Mono12Packed | uint16 | 4095 | 12 bit counts, right-justified |
| Mono16 | uint16 | 65530 | the whole 16 bit range, all low bits used |

The means agree: Mono8 144.7, Mono10 579, Mono12 2317, Mono16 37066, which
are the 12 bit mean divided by 16 and by 4 and multiplied by 16.  The shape
of every frame is `(1024, 1280)`.  The rate does not depend on the format
(exposure limits it), except that Mono16 is about 7 % lower, as twice the
bytes over USB3 would make it.  Found on the way:

- `QGenicamCamera` cannot read `Mono10Packed`: Harvesters does not unpack it
  (1.25 bytes a pixel) and `read()` fails with "cannot reshape array of size
  1638400 into shape (546133,3)", then times out.  The one frame that
  arrives after the switch holds the previous format.  `viva` reads it
  correctly.  Not worth a fix while `viva` is the preferred path.
- A change to a format with another dtype announces nothing: `shapeChanged`
  carries only the width and height, so a consumer learns of the new dtype
  from the frame.
- The first frames after a change of format may be in the old format.
- The screen maps the whole range of the dtype: a 12 bit frame shows 16
  times too dark (a ramp to 4095 shows 2 to 14 of 255); Mono16 shows
  correctly.  `QVideoScreen.levels` sets the range, and now each frame
  brings its own; a range costs about 7 ms a frame at 1280 by 1024 against
  2 ms without.
- Of 16 filters on a `uint16` frame, 4 raise (Canny, Gamma, median
  smoothing, Log exposure: 8 bit lookup tables and OpenCV calls), 5 return
  `uint8` (Laplacian, Sobel, DoG, Pencil sketch, Cartoon, which gives zeros)
  and 7 keep the dtype, though the thresholds are still on a scale of 255.

**Decided 2026-11-04: counts as the camera sends them, and the range travels
with the frame** (`FrameInfo.levels`, cached by the camera and set when the
pixel format changes).  The screen follows the levels of each frame; the
filter pipeline scales a deep frame to 8 bits for every filter that is not
`deep` (`VideoFilter.deep`); an HDF5 recording keeps the levels.  Working on
a Blackfly S with viva on macOS and on Ubuntu 24.04, changing the bit depth
while streaming included.

- [x] **Find out what the camera and `to_numpy()` give.**  Done 2026-11-04
  (the table above), through `viva` and through `QGenicamCamera`.
- [x] **Choose the format in the tree.**  `PixelFormat` is a GenICam
  enumeration, so the tree shows it; changing it while streaming works on a
  Blackfly S with viva (macOS and Ubuntu 24.04, 2026-11-04).  The shape
  signal carries only width and height, so a consumer learns the new dtype
  from the frame (accepted).
- [x] **Make filters `deep`** (2026-11-07).  `VideoFilter.levels` and
  `bounds(frame)`; deep: dark frame, flat field (the reference remembers its
  type), invert, unsharp, DoG, MoMean, Median, MoMedian, Normalize,
  SampleHold, smoothing (not median), global threshold, ROI.  The rest
  (Canny, Gamma, Exposure, Laplacian, Sobel, artistic, blob, circle
  transform, foreground, dejitter, RGB, Otsu and adaptive threshold) get the
  8 bit copy, which is right for those that use lookup tables or 8 bit
  OpenCV calls.  Later, if wanted: Gamma and Exposure as `uint16` lookup
  tables, Laplacian and Sobel with `CV_32F`.
- [x] **Say it for the other consumers of `levels`** (2026-11-07).
  `QSnapshot` saves 16 bit gray PNG/TIFF stretched by the levels; the `.mp4`
  writers scale to 8 bits and say so; `QFilterRack.__call__(frame, levels)`
  and the `Camera()` proxy scale like the pipeline (`prepare`); `QCamcorder`
  has the choice of levels.
- [x] **Walk the pipeline** (2026-11-07).  Screen (levels, `autoLevels`;
  the color map follows the levels), filters (above), snapshot and writers
  (above, HDF5 keeps any dtype and the levels, gray `.avi`/`.mkv` keep 16
  bit), ring of `QRemoteCamera` carries `uint16` and the levels.  The
  overlays work on what the screen shows.
- [x] **Tests** (2026-11-07): `tests/test_deepfilters.py` on counts for
  every deep filter, the pipeline, the rack and the notebook camera, the
  snapshot, both `.mp4` writers, the screen and the camcorder.  Not done: a
  camera of viva-genicam's fake that makes Mono12 (it is not known whether it
  can).
- [x] **A contrast filter for deep frames**: decided 2026-11-07 *not* to
  build a filter; `QVideoScreen.autoLevels` (percentiles, smoothed) shows a
  dim image without changing the counts, and a filter that changes them
  would have to sit after every quantitative stage.

---

## Unified Camera Discovery and Selection

`available_cameras()` lists the cameras of every installed backend that
can be opened, and `QCameraChooser` (in `widgets/`) is a combo box over
that list.  What remains:

- **Switching cameras in `QCamcorder`** — an embedded `QCameraChooser`
  panel in place of the startup argument, so the user can switch cameras
  without restarting.  Switching needs the camera to be closed and opened
  again while the screen, the recorder and the filters keep their
  connections.  Hot-plug was dropped (2026-11-07), so this has no
  machinery to share; it stands on its own and nobody has asked for it.
- **Point-and-click start** (partly done 2026-11-07) — `launch()` shows a
  list of the cameras, by name, when a flag names a backend that lists
  several and `cameraID` leaves the choice open.  Still open: a chooser
  across backends, for a launch with no flag, from `available_cameras()`.
- **Refactor `cameras/chooser.py`** (cleaned and documented, 2026-11-02;
  it is readable now, but the design is unchanged).  It does five jobs:
  the table of backends, importing and probing, creating and opening
  cameras, the command line, and building trees.  If it grows again, split
  it along those lines.  Decide first: which functions are public API
  (`__all__` lists five names, other modules import more), whether a
  camera that does not open should fall back to the noise camera (it did
  so silently and misled two measurements), and one default for the command
  line and `Camera()` (today the command line opens noise and `Camera()`
  opens the first real camera).  `_names` hard-codes OpenCV, and `_probe`
  imports a whole backend to ask if it exists.

---

## Dropped frames  **Planned; not urgent**

`QCamera.read()` returns no frame number, and `QVideoSource` counts
`FrameInfo.index` after the read, so a frame that the camera, its driver or a
`QRemoteCamera` discards leaves no gap.  `QVideoSource`, which reads every
camera, should detect and report this once for all of them:

- [ ] Compare the interval between frames with the usual one.  Use
      `hardwareTimestamp` when the camera has one (`QRemoteCamera` carries
      it), and the arrival time otherwise.  A longer interval means that
      frames were lost.
- [ ] Warn, at a limited rate so that a stalled camera does not flood the
      log, and keep a count that a recorder or a status bar can show.
- [ ] Test with a camera that skips frames and with a slow consumer.

`QCamera` needs no frame counter for this; add one only if a camera can
report its own.

---

## Camera loss  **Viva done 2026-11-07; the other backends open**

Replaces the hot-plug plan of 2026-10-28.  Decided 2026-11-07: QVideo does
**not** reconnect (a solution in search of a problem); restarting the program
is the recovery.  What it must do is fail gracefully and say so: show the
last frame, let everything else carry on, and not flood or spin.

**Built (c1fc375).**  `QCamera._deviceLost(reason)` closes the camera, logs
one error and emits `lost(str)`, which `QVideoSource` passes on.  A closed
camera answers `saferead()` with `(False, None)`, `get()` with `None`, and
refuses `set()`/`execute()` with a warning; a camera counts as open while
`_initialize` runs.  The capture loop waits 50 ms between asks of a closed
camera.  `QCameraTree` disables itself; `QCamcorder` shows the reason in the
status bar and a dialog.  `QVivaCamera` reports the end of its stream as the
loss (a live stream raises when it has no frame, timeouts included, and only
returns `None` after the device has gone).  Documented in
`docs/backends.rst` ("When the device goes"); the conformance suite checks
that every backend answers quietly once lost.

**Measured 2026-11-06** on a Blackfly S, USB, under Viva: unplugging gives
`TransportError: read a frame: the device is disconnected` 40 ms after the
last frame, then `next_frame` returns `None` for ever; the old loop did
1,000,000 reads a second at 100% of a core with one line in the log.
`close()` of the dead device returns at once.

- [ ] **Verify the whole path on the camera.**  Run `python -m QVideo -g`,
  unplug the cable, and look: the dialog, the status bar, the disabled
  tree, the last frame, an idle core.  (The parts were tested with a fake
  and with a script; not the window.)
- [x] **OpenCV** (2026-11-07): a live camera (not a video file) that sends no
  frame for `lossTimeout` seconds (2) is lost; a closed `VideoCapture` is lost
  at once.  Tested with a mock, on the built-in camera (no false loss: 181
  frames in 6 s, longest gap 51 ms) and on a video file played past its end.
  **Tried 2026-11-07 by unplugging a Logitech C920 on macOS (AVFoundation):**
  the reads fail without an exception, each one blocking about 0.5 s;
  `isOpened()` stays `True`, so only the timeout catches it (the loss came
  2 s after the last frame).  Linux (V4L2) is not tried.
- [x] **OpenCV's device numbers did not match the names** (macOS, found
  2026-11-07, fixed the same day).  With the built-in camera and the C920
  attached, Qt listed `{0: FaceTime HD Camera, 1: HD Pro Webcam C920}` (the
  order of plugging in) and OpenCV's index 0 was the C920 (looked at the
  frames).  Now `QOpenCVDevices.devices()` works the index out per platform:
  macOS sorts by the Qt `id()` (= AVFoundation `uniqueID`; the rule agrees
  with two observations here and with the source of `cv2-enumerate-cameras`,
  but is OpenCV's own business and may change); Linux takes the `N` of
  `/dev/videoN`; elsewhere Qt's order.  `QOpenCVCamera(cameraID=...)` takes
  an index, an id or a part of a name.
- [ ] **Still open for OpenCV identity:** Windows (is Qt's WMF order OpenCV's
  MSMF or DirectShow order?) and Linux (V4L2 with several cameras, and the
  Pi's libcamera, are not tried); `Camera()` in a script takes only an
  index (the command line takes a name, and asks when several cameras
  fit); a USB webcam's macOS
  id has no serial number (it holds the port and the vendor and product ids),
  so two cameras of one model are told apart by the port.
- [ ] **The other backends** call `_deviceLost` where their library says the
  device is gone, each tried by pulling a cable.  `QRemoteCamera` knows when
  its worker has gone (`_lost`); Harvesters (`QGenicamCamera`) raises generic
  errors, so classify them only if that backend stays; Picamera is cabled and
  never needs it.
- [ ] **Optional:** stop a running recording with "camera lost" (it stalls
  now; the dialog tells the user to stop it); a placard on the screen; a
  `launch()` option to quit on loss.
- Not planned: reconnection, device identity, replay of settings, starting
  without a camera.  The five decisions of 2026-11-06 that assumed
  reconnection (same device, retry, replay) no longer apply; stopping a
  recording on loss and a placard are still wanted, as optional above.

---

## Analysis Overlays

The new `overlays/` package provides `QTrackpyWidget` and `QYoloWidget`.
Potential additions:

- **`QLorentzMieWidget`** — feed live frames to `pylorenzmie` for
  in-situ holographic characterization (particle radius, refractive
  index); overlay fitted parameters on `QVideoScreen`.
- **`QBlobWidget`** — lightweight blob detector (OpenCV
  `SimpleBlobDetector`) as a zero-dependency alternative to trackpy
  for quick particle counting.
- **`QFaceWidget`** — face / landmark detection overlay using
  MediaPipe or dlib; useful for human-factors and gaze-tracking demos.

---

## Screen() API and Composable Vision Pipelines

`Camera()` (`interactive/camera.py`) already proves the "minimal code" factory
pattern works well for QVideo: discover a backend, return something
usable immediately, and — in Jupyter — stay awaitable/interactive.
Two follow-on ideas from a 2026-07-10 discussion, in increasing order
of ambition.

### `Screen()` — a display counterpart to `Camera()`

`_CameraProxy.live_view()` already solves the hard part of this in
miniature: it streams JPEG-encoded frames into an `ipywidgets.Image`
via an `asyncio` background task, with no `QVideoScreen`/Qt widget and
no `QApplication` event loop involved. That capability is currently
trapped as a method on the camera proxy — you can only view what
`Camera()` opened.

- **Factor it into a standalone `Screen(source)`** accepting any
  `QCamera`, `QVideoSource`, or `_CameraProxy` — anything with the
  `newFrame`/`fps` duck type `QVideoScreen.source` already accepts.
  Lets you view a filtered
  pipeline, DVR playback, or a composited overlay feed, not just a
  raw camera.
- **Environment-dependent implementation**, mirroring the
  `IPython.get_ipython()` check `_CameraProxy._select()` already does:
  - **Jupyter notebook** — `ipywidgets.Image` + `asyncio` task, same
    mechanism as `live_view()`. This works because `ipykernel` runs a
    single persistent `asyncio` event loop that drives both cell
    execution and any background task scheduled on it — the
    frame-update loop keeps running between cells without blocking.
  - **IPython terminal** — a real `QVideoScreen` widget kept live via
    IPython's `%gui qt` input-hook (the same mechanism that makes
    interactive `matplotlib` work), if the user has that integration
    enabled.
  - **Plain script / `python` REPL** — no persistent event loop and
    no input-hook mechanism exists here, and Qt widgets must be
    created/touched on the main thread (strictly enforced on macOS),
    so there is no clean way to get a live-updating display *and* a
    responsive prompt at the same time. Falls back to the traditional
    blocking `screen.show(); app.exec()`.
  - **Takeaway:** "watch video while still typing commands" is a
    genuine capability, but it is a Jupyter-notebook-kernel property
    (or an IPython-terminal-with-`%gui qt` property), not something
    `Screen()` can generalize to every command line.

### Composable pipelines: `Camera() -> Filter() -> Screen(overlay=...)`

Prompted by `Screen()`: could a full vision system — camera, filter
chain, live display, detection overlay — be assembled in a few lines,
the way `Camera()` already assembles a camera in one? The pieces
mostly already exist; what's missing is a thin factory layer over
them:

- **`Filter()` factory, analogous to `Camera()`/`Screen()`** — this is
  now `QFilterPipeline` (`lib/QFilterPipeline.py`): it wraps a source (and
  optionally a `QFilterRack`), filters on a worker thread, and
  re-emits `newFrame(ndarray, FrameInfo)` with `.fps` and `.shape`, so
  it feeds a `Screen()` or a DVR in turn.  A public
  `Filter(source, *filters)` would be a one-line convenience over it.
- **`Screen(source, overlay=...)`** — construct the requested overlay
  widget (`QYoloWidget`, `QTrackpyWidget`, ...), wire
  `overlay.source = source`, and call
  `screen.addOverlay(overlay.overlay)` automatically instead of the
  multi-line manual wiring every demo currently repeats.
- **The real obstacle: overlay rendering is Qt-only today.**
  `QYoloOverlay`/`QTrackpyOverlay` draw via
  `pyqtgraph.GraphicsObject.paint()` (a `QPainter` call) — that only
  works inside a real `QVideoScreen` widget. The Jupyter/`live_view()`
  path JPEG-encodes a bare numpy frame with no `QPainter` involved, so
  `overlay=` can't work there without either (a) a second,
  numpy/`cv2`-based rendering path per overlay (e.g. `cv2.rectangle`
  for `QYoloOverlay`), or (b) reusing the existing
  `QWidget.grab()`-based compositing machinery of
  `QVideoScreen.screenshot` to
  rasterize the live Qt screen + overlay into an image before
  streaming it to `ipywidgets.Image` — which still requires a real
  (if invisible) `QVideoScreen`/`QApplication` to exist even in the
  Jupyter case, unlike the current pure-`ipywidgets` `live_view()`.
- **Optional sugar, secondary to the factory-call form above:**
  operator overloading (e.g. `cam | GaussianFilter() | Screen()`) for
  a more pipeline-like feel. Worth considering only once the plain
  `Screen(Filter(cam, ...), overlay=...)` factory composition is
  solid — avoid the overload sugar becoming the first thing that has
  to be designed.

### Filters emit results; overlays subscribe instead of detecting

Today `QYoloWidget`/`QTrackpyWidget` connect to `source.newFrame`
directly and run their own detection, independent of whatever
`QFilterPipeline` is doing. That's a latent
correctness gap: if a display filter crops or geometrically
transforms the frame, the overlay's boxes are computed in raw-source
coordinates but drawn on top of a transformed frame. It also
duplicates work — `overlays/yolo.py`'s `_YoloWorker` is a hand-rolled
`QThread` + drop-frame implementation of the latest-wins handoff that
`QFilterPipeline` now provides.

Proposed fix: move detection into a filter stage — e.g.
`YOLOFilter(VideoFilter)` sitting in the rack, pass-through on
the image, emitting a results signal — so detection runs on the frame
*as it exists at that point in the pipeline*, staying correctly
aligned with what's actually displayed, and one inference pass can
feed the overlay, the planned
`QAnalysisWriter`, and a live stats readout simultaneously instead
of each running its own detector.

- **No base-class change needed.** `QVideoFilter` widgets are
  `QObject` subclasses; a filter's widget can declare its own
  `Signal` directly (`YOLOFilter.detectionsReady = QtCore.Signal
  (object)`) with zero changes to the shared base. Baking a results
  signal into `VideoFilter` itself would be the
  wrong call — those classes back nearly every filter in the project,
  and only detector-style filters (YOLO, Trackpy, maybe a future
  blob/DNN filter) ever need one; the other dozen-plus filters
  (Gaussian, threshold, gamma, ...) would carry a signal they never
  use.
- **A small opt-in convention still helps the registration side.**
  The overlay needs to find "the YOLO filter" in the rack and connect
  to it without special-casing every filter class by name. That only
  needs a consistent signal name (`resultsReady`) or a tiny marker
  mixin (`class ResultsFilter: resultsReady = QtCore.Signal(object)`)
  that just `YOLOFilter`/`TrackpyFilter` additionally inherit from —
  additive and opt-in, not a change to `VideoFilter`.
- **Registration/enable API needed on `QFilterRack`** — the overlay
  needs to find-or-create the detector filter instance by name/type,
  connect to its results signal, and enable it if it isn't already
  active; if the user later disables or removes that filter from the
  rack, the overlay needs to notice and clear its drawn results rather
  than show stale boxes.
- **Migration cost:** a real refactor of two shipped widgets
  (`QYoloWidget`, `QTrackpyWidget`) plus their tests.  A slow detector
  would run on the pipeline's single worker thread and set the pace of
  every later filter, so a detector probably wants its own pipeline.
- **Natural pairing with the YOLO `cv2.dnn` test case** above — worth
  designing the filter/signal split and the torch-free backend
  together rather than migrating YOLO twice.

---

## Remote display and control: an iPad as the instrument panel

Idea (2026-10-26): watch and steer an experiment from an iPad over Wi-Fi.
A native iOS port is not practical: PySide6 runs on iOS only since Qt 6.12
and is early, and there are no iOS builds of OpenCV, `psutil` or `h5py`.
iOS also cannot load a GenTL `.cti` producer or reach USB3 Vision and GigE
cameras, so only UVC webcams would work.  Keep the camera and the
acquisition on the host and make the iPad a client in its browser.

- **Expected display rate**, estimated from JPEG sizes measured on a Mac
  (8-bit gray, OpenCV quality 95; not yet measured over Wi-Fi): 640x480 is
  88 KB per frame, 21 Mbit/s at 30 fps; 1280x720 is 217 KB, 51 Mbit/s;
  1920x1080 is 498 KB, 117 Mbit/s.  Quality 80 needs a half to a third of
  that.  A good Wi-Fi 5 or 6 link sustains 100-400 Mbit/s, so expect a
  steady 20-30 fps up to 1080p, and a delay of about 60-150 ms from sensor
  to screen.  That suits watching and steering, not a feedback loop, which
  stays on the host.  Faster than 30-60 fps needs a video codec (H.264 or
  HEVC over WebRTC), not JPEG.
- **`Camera.live_view` is not built for a network.**  It sets an
  `ipywidgets.Image` every 1/30 s and sends each frame through the Jupyter
  connection as base64, without asking whether the client kept up, so on a
  slow link the picture falls behind in time instead of dropping frames.
- **A streaming component**: the camera keeps its full hardware rate and
  only the display is limited; send the newest frame only (the idea of
  `QFrameRelay`) and wait for the client to acknowledge before sending the
  next; binary frames over a WebSocket, or MJPEG over HTTP, with the size
  and quality chosen to fit the link; overlays (particle markers, an ROI)
  sent as data and drawn by the client; controls through the existing
  property interface.
- **To do first**: prototype the stream and measure it on David's network
  with an iPad, comparing 720p and 1080p and qualities 80 and 95.

---

## DVR Enhancements

- **Metadata sidecar** — write a JSON file alongside each recording
  containing camera settings, frame rate, and timestamps so recordings
  are self-describing without opening the HDF5 file.
- **Playback speed control** — the DVR player currently plays at
  real time; add a rate spinbox for slow-motion and fast-forward review.
- **Delivered frame rate: settled on a FLIR camera (2026-10-27).**
  `QCamera.actualFps` (4.7.0) is the rate that a camera delivers, beside
  `fps`, the rate that was asked for, and `QVideoSource.fps` reports it.
  `QGenicamCamera` reads `AcquisitionResultingFrameRate` (then the older
  names) and falls back to `fps`.  On the FLIR camera the node is the
  delivered rate, not the maximum: 32.640 against 32.63 measured, and
  13.039 against 13.04 measured with a 2.5-frame exposure.  With
  `AcquisitionFrameRateEnable` off the camera free-runs and
  `AcquisitionFrameRate` is read-only and does not follow the exposure, so
  `fps` alone would mislead; no change to `actualFps` is needed.  Not
  tested: whether the node falls when the camera's buffers overrun, and
  whether a request above the maximum is clamped (it needs the frame-rate
  enable).  OpenCV cameras use the rate that the driver reports; QVideo
  does not measure it (decided 2026-10-26).  The file header ignores the
  interval setting (`nskip`) on purpose: recording every Nth frame plays N
  times faster, a time-lapse (decided 2026-10-27); transcode to change it.
---

## Core dependency: OpenCV

`opencv-python` stays a core dependency: it is too pervasive to make
optional (camera backend, DVR writer and reader, filters, resolution
probing).  Accepting `opencv-python-headless` as an alternative is not yet
possible via PEP 508; document it as a note for headless deployments if
requested.

---

## Testing and Quality

- **Hardware-in-the-loop tests** — optional test suite (skipped when
  hardware is absent) that exercises real cameras to catch
  driver-specific regressions.
- **Performance benchmarks** — track frame-drop rate and latency across
  commits for high-frame-rate cameras.

---

## Documentation Gaps  **Done 2026-11-06**

Some pages of the ReadTheDocs site are API listings with little prose.
Fill the gaps so that a page gives a user enough context to use the module
without reading the source.

- **Camera backends** (`docs/api/cameras.rst`) — an introductory paragraph
  per backend covering the target hardware, the SDK prerequisites, the
  install command, and a minimal usage snippet.
- **DVR** (`docs/api/dvr.rst`) — describe the recording formats (HDF5 with
  timestamps and lossless compression; video files written by PyAV or
  OpenCV, and the codec each one uses), the `.newFrame` / `.fps`
  duck-typing contract, and a short wiring example.
- **Overlays** (`docs/api/overlays.rst`) — add a paragraph covering
  `QVideoScreen.composite` and composite-frame recording.

---

## Broken PyPI Page Graphic  **Done 2026-04-25; checked 2026-11-06**

Fixed in 4672f6d: `README.md` uses the absolute raw.githubusercontent.com
URL of `docs/dvrdemo.png`, which answers 200.  Confirm on the PyPI page
after the next release.  The original report:

The image on the QVideo PyPI page fails to render.  PyPI serves
`README.md` as the project description but does not resolve relative
image paths or GitHub-hosted raw URLs that require authentication.

- Identify the broken `![…](…)` reference in `README.md`.
- Replace the path with an absolute `https://raw.githubusercontent.com/…`
  URL pointing to the `main` branch so PyPI can fetch it directly.
- Verify the fix locally with `twine check dist/*` (renders the long
  description and flags broken markup) before the next release.

---

## Distribution

- Add references to relevant literature in `README.md` (holographic
  video microscopy, particle tracking, YOLO object detection).
- Conda-forge recipe for users who prefer conda environments.

---

## OpenCV 5 Feature Adoption

OpenCV 5 improves property setting (see the platform-specific capture
backend selection added in `cameras/OpenCV/_camera.py`).  Findings from
a full-codebase review (2026-07-10):

- **Lower priority / cosmetic**, no action needed yet:
  - Python bindings now accept keyword arguments broadly
    (`cv2.fn(threshold=0.5)`) — could clean up the more
    parameter-heavy calls in `threshold.py`, `exposure.py`,
    `artistic.py`.
  - `warpAffine`/`remap` interpolation was revised for accuracy in
    5.x — affects `dejitter.py`'s `cv2.warpAffine` call; output will
    shift slightly (not a bug), relevant only if chasing bit-exact
    reproducibility across OpenCV versions.
  - Redesigned DNN engine / ~80% ONNX coverage doesn't apply yet:
    `overlays/yolo.py` uses `ultralytics` directly, not `cv2.dnn`.
    OpenCV 5.0 shipped 2026-06-04 with ONNX operator coverage jumping
    from ~22% to ~80%, and the dev environment is now actually on
    `cv2==5.0.0` (confirmed `cv2.dnn.readNet`,
    `cv2.dnn.ENGINE_AUTO`/`ENGINE_NEW`/`ENGINE_ORT`,
    `cv2.dnn.NMSBoxes` all present). A YOLOv8/v11 `.onnx` export now
    loads directly via `cv2.dnn.readNet(...)`, giving a genuinely
    torch-free detection path.
    Not yet prototyped against QVideo's `_YoloWorker`; would need
    manual output decoding + `cv2.dnn.NMSBoxes` in place of
    `ultralytics`' built-in postprocessing.
  - No legacy C API (`CvMat`/`IplImage`/`cv2.cv`) usage anywhere in
    the codebase — confirmed by grep, so the biggest OpenCV 5
    breaking change doesn't touch QVideo at all.
  - `numpy`/`opencv-python` are both unpinned in `pyproject.toml`, so
    NumPy 2.x support in OpenCV 5 needs no dependency-constraint
    action.

---

## OpenCV DNN Framework — New Capabilities

OpenCV 5.0 (released 2026-06-04) rewrote the `cv2.dnn` engine and
raised ONNX operator coverage from ~22% to ~80% (see "OpenCV 5
Feature Adoption" above). The dev environment is confirmed on
`cv2==5.0.0`. Survey of what this opens up for QVideo, roughly
ordered by value vs. effort:

- **Torch-free YOLO backend (test case — start here)** — see below.
- **Face/landmark detection with zero extra dependencies** —
  `cv2.FaceDetectorYN` (the YuNet model, `cv2.dnn` under the hood,
  Apache-2.0) as the implementation for the planned `QFaceWidget`
  (see "Analysis Overlays") instead of MediaPipe or dlib.
- **Learned segmentation as a `QForegroundEstimator` option** — an
  ONNX segmentation model (U-Net/DeepLabV3-style) alongside the
  existing classical MOG2 method, selectable per use case.
- **Super-resolution filter** — `cv2.dnn_superres`
  (EDSR/FSRCNN/ESPCN/LapSRN) as a new `VideoFilter` for upscaling
  feeds from low-res USB cameras.
- **Text/OCR overlay** — `cv2.dnn_TextDetectionModel` /
  `TextRecognitionModel` (EAST + CRNN) to read burned-in timestamps,
  instrument displays, or labels in the field of view.
- **Monocular depth estimation** — a lightweight MiDaS-style ONNX
  model as a software fallback pseudo-depth overlay where dedicated
  depth hardware (Kinect/RealSense, see "New Camera Backends") isn't
  available.
- **VLM/natural-language frame captioning** — OpenCV 5 bundles VLM
  support (Qwen 2.5, PaliGemma, etc.); a "describe this frame" widget
  could auto-annotate recordings or flag notable events during
  long unattended acquisitions.
- **Anomaly/novelty detection** — a small autoencoder-style ONNX
  model flagging frames that deviate from a learned baseline; pairs
  with the hot-plug / long-duration-recording themes above.
- **Foundational: a shared helper, `lib/dnn.py`** (design, 2026-11-06;
  replaces the `DNNFilter`/`QDNNOverlay` base-class pair proposed
  earlier).  See "Design: filter, overlay or both" below.  Build this
  first, with the YOLO test case as its first user.

### Design: filter, overlay or both  **Decided 2026-11-06**

Where a model goes depends on what it outputs.  A filter transforms
frames; an analysis produces data (the same ground on which a trackpy
filter and a YOLO filter were rejected).

- **Image in, image out: a `VideoFilter`**, in the pipeline between the
  source and its consumers.  Super-resolution, learned segmentation (an
  option next to `QForegroundEstimator`), depth maps, learned denoising.
  These models are slow, so they subclass `AsyncVideoFilter`, which
  already drops frames.
- **Image in, structured data out: an overlay** (`QOverlayWidget`), drawn
  by the screen and emitted as a signal for `QAnalysisWriter`.  YOLO
  detection, faces and landmarks (`FaceDetectorYN`), OCR, captions,
  anomaly scores.
- **The YOLO test case is neither.**  It stays `QYoloOverlay`; the change
  is inside `_YoloWorker`, which accepts either detector (`ultralytics` or
  an ONNX model through `cv2.dnn`), with a backend choice in the widget.
- **No base-class pair.**  What the two kinds share is not a filter or an
  overlay: a plain, non-Qt helper in `lib/dnn.py` (like `imageops`) that
  loads the model, calls `blobFromImage`, picks the engine, runs the
  forward pass and offers a postprocessing hook.  A filter and an overlay
  worker each use it.  No parallel hierarchies, no Qt in the model code,
  and it is testable without a GUI with a tiny ONNX model.  It takes the
  engine or backend as a parameter, `ENGINE_AUTO` by default.
- A model can produce both (a segmentation network gives a mask and
  regions).  Start with the output that is needed; the overlay worker may
  call the same helper later.

First step: `lib/dnn.py` and the `cv2.dnn` backend of `_YoloWorker`, which
exercises the helper on a real model.

**Done 2026-11-06 (uncommitted until reviewed):** `lib/dnn.py` (`DNN`,
`letterbox`, `prepare`), the OpenCV backend of `_YoloWorker`
(`backend='auto'|'ultralytics'|'opencv'`, `imgsz`, `names`; `decode()` for
the YOLOv8-and-later layout `(1, 4 + nc, N)`), tests with a tiny ONNX
file written by hand (`tests/onnxfile.py`), docs, and `YoloDemo`
(`--model x.onnx --imgsz N --names a,b --backend ...`). **Tested 2026-11-06 on
a real export** (`yolo11n.pt` to ONNX with Ultralytics 8.4, opset 18): the
OpenCV backend finds the same five objects as `ultralytics` on `bus.jpg`, with
the same labels; boxes differ by up to 9 pixels (square padded input against
Ultralytics' minimal padding) and the weakest score is 0.4 against 0.6. Speed
on the dev machine's CPU (10 cores): 27 ms a frame with OpenCV, 34 ms with
`ultralytics`. Importing `ultralytics` sets `cv2.setNumThreads(0)`, which made
OpenCV four times slower (98 ms); the import is lazy now and restores the
threads. `yolo26n.pt` exports with the same `(1, 84, 8400)` layout (Ultralytics
8.4, default options) and reads the same way: same five objects, 27 ms, so no
change to `decode()` was needed; an export made with other options may differ.
**Not yet done:** the filters (super-resolution, learned segmentation, depth),
which use `DNN` the same way.

**Speed on CUDA machines.**  The standard `opencv-python` wheels are
CPU-only: `DNN_BACKEND_CUDA` needs OpenCV built from source with CUDA, so
an NVIDIA GPU gives no speedup with the pip wheel.  `torch` wheels bundle
CUDA (and Apple MPS), so `ultralytics` stays as the opt-in accelerated
backend.  For YOLO-class models a GPU is typically several times faster
than the CPU (not measured here); for small models such as `yolo11n` at a
camera's frame rate, the copy of each frame to the GPU can cancel it.
`cv2.dnn` has no Metal path on a Mac and no GPU option on a Raspberry Pi;
the CPU is enough for small models there.

- [ ] **Test ONNX Runtime through OpenCV 5** (`cv2.dnn.ENGINE_ORT`) on a
      CUDA machine: `onnxruntime-gpu` wheels ship with CUDA, and the CoreML
      provider covers Apple hardware.  If it works with the pip wheel, it
      gives GPU inference with neither `torch` nor a source build.  Not
      yet checked whether the engine is usable that way.

### Test case: torch-free YOLO via `cv2.dnn`

`overlays/yolo.py`'s `_YoloWorker` currently hard-requires
`ultralytics`, which pulls in `torch` — the heaviest optional
dependency in the project. Goal: add a `cv2.dnn`-based backend as a
**second option alongside** the existing `ultralytics` path, not a
replacement, and write up detailed instructions so users can prepare
their own ONNX exports. Findings so far:

- **Keep `torch`/`ultralytics` as an opt-in accelerated backend.**
  OpenCV 5's new DNN engine is CPU-only at launch (its hardware
  acceleration is CPU-side: Intel IPP/AVX, Arm KleidiCV, Qualcomm
  FastCV, RISC-V RVV). Real GPU acceleration for `cv2.dnn`
  (`DNN_BACKEND_CUDA`) requires building OpenCV from source with CUDA
  — the standard `opencv-python`/`opencv-python-headless` pip wheels
  don't include it. `torch`'s pip wheels bundle CUDA (and Apple MPS)
  out of the box. So `cv2.dnn` should be the lightweight default;
  `ultralytics`/`torch` remains the answer for users who have an
  NVIDIA GPU and want maximum throughput.
- **Reimplementation work needed:** `ultralytics`'s Python API does
  box decoding, confidence filtering, and NMS internally.  A
  `cv2.dnn` path needs to redo that manually with
  `cv2.dnn.NMSBoxes` plus manual decoding of the YOLO output tensor
  layout — which differs between YOLO versions/export conventions,
  so the decoding logic must be pinned to a specific export
  convention and documented as such.
- **Do not bundle a `yolov11n.onnx` file in the QVideo repo or
  package as a default fallback.** Ultralytics licenses all
  pretrained YOLO checkpoints (including exports derived from them)
  under AGPL-3.0 by default; their own license page states that using
  the models obligates releasing the complete corresponding source of
  "the larger application" under AGPL-3.0 unless the user holds an
  Ultralytics Enterprise license. That is a materially stronger
  copyleft obligation than QVideo's own GPL-3.0-or-later, and
  redistributing the weights as a bundled default could pull
  downstream users — especially commercial ones — into those terms
  without them realizing it. Also a plain repo-hygiene concern:
  bundling a binary model blob conflicts with the "media files belong
  only under `docs/`" / no-build-step / small-footprint conventions
  already in place (see "Reduce Core Dependencies").
  Alternatives to write into the user instructions instead:
  - Auto-download-on-first-use from a canonical source (mirroring
    what `ultralytics.YOLO(model_name)` already does), caching
    locally, with a clear notice of the AGPL-3.0 terms and a pointer
    to Ultralytics' Enterprise licensing page for commercial users
    who need to avoid them.
  - Document how a user exports their own `.onnx` from a YOLO
    checkpoint they already have rights to use (`torch` is required
    for the one-time export step even though it's not needed at
    inference time — "torch-free" applies to runtime, not model
    preparation).
  - Investigate whether the [OpenCV Zoo](https://github.com/opencv/
    opencv_zoo) has a permissively-licensed (Apache-2.0) general
    object-detection model suitable as a truly redistributable
    default, separate from anything YOLO/Ultralytics-derived.
