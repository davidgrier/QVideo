# filters: image-processing steps for live video

Each module defines a `VideoFilter` (the processing, with no Qt widgets)
and usually a `Q...Filter` (a `QVideoFilter` with the controls).  A filter
is a callable: `output = filter(frame)`.  The `Q...Filter` widgets go into
a `QFilterRack`, which runs the switched-on filters on a worker thread.

In a notebook, `Filter()` lists the filters and `Filter('Canny')` builds
one; `camera.filters = [...]` applies them to `camera.read()`.

A stateless filter overrides `process(frame)`.  A filter that keeps state
overrides `add` and `get`.  No filter owns a thread.  Prefer OpenCV calls
and lookup tables to NumPy expressions on whole float images.

`docs/extending.rst` ("Filters") walks through writing one, and
`invert.py` is the shortest example.
