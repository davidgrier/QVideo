# demos: recipes for building applications

Each demo is a widget that takes a camera tree and adds one idea to the
demo before it.  `demo.py` is the starting point: live video beside the
controls of the camera.  Read the others in the order that
`demos/__init__.py` lists them.

Run one with, for example, `python -m QVideo.demos.demo -c` (`-c` selects
an OpenCV camera; without a flag you get the noise camera).

To write an application, copy the demo that is closest, override
`_setupUi()` (calling `super()._setupUi()` first) and connect your widgets
in `_connectSignals()`.  The full application is `QCamcorder.py`.
