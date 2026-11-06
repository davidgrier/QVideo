# lib: the classes that you subclass

`lib` holds the base classes of QVideo and the machinery that they run on.
Applications, backends and filters are built by subclassing them, which
gives every part of the project the same structure and makes it easy to
extend.

| You want to add | Subclass | Where it goes |
|-----------------|----------|---------------|
| a camera | `QCamera` (and `QVideoSource`, `QCameraTree`) | `cameras/` |
| a filter | `VideoFilter` (and `QVideoFilter` for its controls) | `filters/` |
| a calibration filter | `ReferenceFilter` | `filters/` |
| an overlay | `QOverlayWidget` | `overlays/` |
| a file format | `QVideoWriter`, `QVideoReader` | `dvr/` |
| an application | a widget that takes a `QCameraTree` | `demos/` |

The rest of `lib` is what these classes need to work together: the thread
that reads a camera (`QVideoSource`), the display (`QVideoScreen`), the
filter pipeline and rack, the frame types and the errors.  `imageops` and `dnn` are plain helpers
without Qt: `dnn.DNN` runs a network with OpenCV for the filters and
overlays that need one.

**A file belongs here if it is a base class, or the machinery of one:**
the classes that applications subclass, and what every application
uses, such as `launch()` and `QSnapshot`, which any project can attach to
a source.  `QCameraOpener` opens the camera in a thread, for `launch()` and
for programs that start more than a camera.  A finished widget that nobody
subclasses goes in `widgets/`.  The notebook interface is in
`interactive/`, and the table of camera backends and the command-line
chooser are in `cameras/`.

`remote/` is the one subpackage: `QRemoteCamera` and the worker process
that it starts, for cameras whose library freezes the interface (see its
`__init__.py`).

`lib` does not import the packages above it, with one exception: `launch()`
opens the camera that the command line names through
`cameras/chooser.py`, because starting an application is the job of the
layer that knows every camera.  Nothing else in `lib` imports
`cameras`, `filters` or `demos` when it loads.

See `docs/architecture.rst` for how the layers fit together and
`docs/backends.rst` and `docs/extending.rst` for how to extend them.
