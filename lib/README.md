# lib: the classes that you subclass

`lib` holds the base classes of QVideo and the machinery that they run on.
Applications, backends and filters are built by subclassing them, which
gives every part of the project the same structure and makes it easy to
extend.

| You want to add | Subclass | Where it goes |
|-----------------|----------|---------------|
| a camera | `QCamera` (and `QVideoSource`, `QCameraTree`) | `cameras/` |
| a filter | `VideoFilter` (and `QVideoFilter` for its controls) | `filters/` |
| a file format | `QVideoWriter`, `QVideoReader` | `dvr/` |
| an application | a widget that takes a `QCameraTree` | `demos/` |

The rest of `lib` is what these classes need to work together: the thread
that reads a camera (`QVideoSource`), the display (`QVideoScreen`), the
filter pipeline and rack, the frame types and the errors.

**A file belongs here if it is a base class, or the machinery of one.**
A finished widget or tool that nobody subclasses does not.  The notebook
interface is in `interactive/`, and the table of camera backends is
`cameras/registry.py`.

See `docs/architecture.rst` for how the layers fit together and
`docs/backends.rst` and `docs/extending.rst` for how to extend them.
