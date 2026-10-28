Widgets
=======

Finished widgets that an application places beside the video.  See
``widgets/README.md`` for what belongs here.

QHistogramWidget
----------------

:class:`~QVideo.widgets.QHistogramWidget.QHistogramWidget` shows the live
histogram of the pixel intensities on a screen.  Its draggable handles set
the range of intensities that the screen displays.  It watches the screen
and needs no connection to the camera; see
:class:`~QVideo.demos.histogramdemo.HistogramDemo`.

.. automodule:: QVideo.widgets.QHistogramWidget
   :members:

QUniformityWidget
-----------------

:class:`~QVideo.widgets.QUniformityWidget.QUniformityWidget` plots the mean
intensity along x and along y for every frame that the screen displays.
Flat traces mean that the illumination is uniform.  See
:class:`~QVideo.demos.uniformitydemo.UniformityDemo`.

.. automodule:: QVideo.widgets.QUniformityWidget
   :members:

QScrollPanel
------------

:class:`~QVideo.widgets.QScrollPanel.QScrollPanel` shows a panel of controls at
its natural size and adds a vertical scroll bar when the window is too short
for it.  :class:`~QVideo.QCamcorder.QCamcorder` puts its controls in one, so
that applications built on it, such as the filter rack and combined demos,
work on a small screen.

.. automodule:: QVideo.widgets.QScrollPanel
   :members:
