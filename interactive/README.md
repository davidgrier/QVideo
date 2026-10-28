# interactive: QVideo without a window

`Camera()` finds a camera and returns an object that reads frames:

```python
from QVideo import Camera, Filter

camera = await Camera()           # or Camera('OpenCV') in a script
camera.filters = Filter('Smoothing', 'Canny')
camera.live_view()                # in a notebook
frame = camera.read()
```

| Module | Contents |
|--------|----------|
| `camera.py` | `Camera()` and the proxy that it returns |
| `filter.py` | `Filter()`: list filters and build them by name |
| `widgets.py` | the `ipywidgets` front end: chooser, controls, live view |

Only `widgets.py` imports `ipywidgets`, and only when a notebook feature is
used, so `Camera()` works in a plain script.  See the chapter "Using QVideo
in Jupyter" in `docs/jupyter.rst`.
