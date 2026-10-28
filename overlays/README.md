# overlays: graphics drawn over live video

An overlay analyzes frames and draws its results on a `QVideoScreen`:
`QTrackpyOverlay` finds particles with trackpy and `QYoloOverlay` detects
objects with a YOLO network.  Each has a widget (`Q...Widget`) with its
controls.

Overlays need packages that most users do not install, so the modules are
imported on first use.  Install them with `pip install "QVideo[overlays]"`.

`docs/extending.rst` ("Overlays") explains how to write one.
