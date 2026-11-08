Stability
=========

QVideo is used in laboratory programs that run for years.  This page says
what a program can count on when it upgrades QVideo, and what it cannot.

The policy applies from the release that contains this page.  Releases
before it changed names without notice (4.15.0 removed three without a
shim); the CHANGELOG records each.

Version numbers
---------------

QVideo follows `Semantic Versioning <https://semver.org>`_.  In
``MAJOR.MINOR.PATCH``:

* a **patch** release fixes bugs and nothing else;
* a **minor** release adds features, and may deprecate; it keeps everything
  that is *stable* (below) working;
* a **major** release may remove what a minor release deprecated, and
  change what was promised.

What the word "public" covers
-----------------------------

Not everything in the package is promised.  There are three levels.

**Stable.**  The promise below covers:

* the top-level ``QVideo.Camera``, ``QVideo.Filter`` and
  ``QVideo.available_cameras``;
* the classes, functions and constants that a package exports in its
  ``__all__`` and that the :doc:`API pages <api/lib>` document, except what
  the next level lists:
  ``QVideo.lib`` (``QCamera``, ``PropertySpec``, ``QVideoSource``,
  ``FrameSource``, ``QVideoScreen``, ``QFilterPipeline``, ``QFilterRack``,
  ``VideoFilter``, ``QVideoFilter``, ``QVideoReader``, ``QVideoWriter``,
  ``FrameInfo`` and the others), ``QVideo.dvr`` and ``QVideo.dvr.formats``,
  ``QVideo.filters``, and the camera and tree class of each backend;
* the **contract of what you subclass**: the methods a backend overrides
  (``_initialize``, ``_deinitialize``, ``read``) and calls
  (``registerProperty``, ``registerMethod``, ``_deviceLost``), the hooks a
  filter, reader or writer implements, and what they may assume
  (:doc:`backends`, :doc:`extending`);
* **signals**, with the types of their arguments;
* the **command line**: the flags of ``python -m QVideo`` and of the demos;
* **files**: a recording that QVideo wrote can be read by every later
  release.  An HDF5 file records its format version, and the reader keeps the
  earlier versions; the JSON sidecar of the other formats keeps its keys.

**Provisional.**  These may change in a minor release.  The CHANGELOG says
so when they do, but there is no deprecation period:

* ``QCamcorder``, the demos and everything in ``demos/``;
* the overlays (``QTrackpyWidget``, ``QYoloWidget``) and the notebook
  widgets of ``QVideo.interactive`` (``live_view``, ``controls``), but not
  the three names listed first above;
* ``QWebScreen`` and its protocol (:doc:`streaming`);
* ``QRemoteCamera``, its protocol, and the node-map methods that only the
  GenICam backends have (``nodeTree``, ``states``, ``hasNode``);
* a backend that the compatibility page lists as not tested, and PySide6.

**Private.**  A name that begins with an underscore (a method, an attribute,
a module such as ``cameras/Genicam/_nodes.py``), and anything that no API
page documents, can change at any time.  A subclass that overrides a
documented hook is covered; one that calls a private method of its parent is
not.

The promise
-----------

For what is **stable**:

#. **Nothing is removed or renamed, and no signature or signal changes in a
   way that breaks a caller, except in a major release.**  Adding a keyword
   argument with a default, or a new signal, is not a break.
#. **The old way works for a whole minor release first.**  A name that is to
   go is kept for at least one minor release, in which it works as before and
   raises a ``DeprecationWarning`` that names the replacement.  It is
   removed no earlier than the next major release.  The retired
   ``Q<Name>Source`` classes of the backends are an example: they still work
   (``cameras/_deprecated.py``) and say what to use.
#. **A subclass keeps working.**  A minor release does not add an abstract
   method, and does not change when a hook is called or what it must return.
   A new hook comes with a default that does nothing (``QCamera._changes``
   did).
#. **Defaults change only with notice.**  A new default for a documented
   parameter is a break.

Three kinds of change are not breaks, and a minor release may make them:

* a **bug fix**: behavior that the documentation never promised, or that
  contradicted it;
* the **support** that ends: a Python version is dropped after its end of
  life, and a Qt binding when its library stops being maintained, each
  announced in the CHANGELOG one minor release ahead;
* **speed and memory**, and the wording of messages and log lines.

A change that must break a stable name outside a major release (a security
fix, or a platform that makes the old behavior impossible) is listed in the
CHANGELOG under **Breaking**, with what to do.

What QVideo does not promise
----------------------------

* **Hardware.**  A backend works with the cameras and the platforms of the
  :doc:`compatibility` page.  A vendor's SDK or a new operating system may
  stop it, and QVideo cannot hold that back.
* **Timing.**  The order in which signals from different threads arrive, and
  how many frames a throttled consumer sees (``QVideoScreen``,
  ``QFrameRelay`` and a pipeline of ``depth=1`` drop frames by design).
* **Dependencies.**  The minimum version of a dependency can rise in a minor
  release when a fix needs it.

For contributors
----------------

A change to a stable name takes four things, in the same pull request:

#. the old name still works and warns, with a test that checks the warning
   (``tests/test_deprecated_sources.py`` shows how);
#. a CHANGELOG entry under **Deprecated** (minor release) or **Breaking**
   (major release, or an exception above);
#. the docstring and the API page say what replaces it;
#. the new name is the one the demos and the documentation use.

A change that adds to the stable set (a new export, a new hook) is a promise:
make it only when you mean to keep it, or keep it private or provisional
until you do.
