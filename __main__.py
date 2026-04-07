'''Entry point for ``python -m QVideo``.

Launches :class:`~QVideo.QCamcorder.QCamcorder`, the full camcorder
application with video screen, camera controls, and DVR.

Usage::

    python -m QVideo [-b|-c|-f|-i|-m|-p|-r|-v] [cameraID]

See :mod:`QVideo.QCamcorder` for the full list of camera flags.
'''

from QVideo.QCamcorder import main

main()
