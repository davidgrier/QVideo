# widgets: finished widgets for an application

A widget here is complete and nobody subclasses it: an application places
it in a window.  `QHistogramWidget` shows the histogram of the pixel
intensities that a `QVideoScreen` displays and sets the range of the
display, `QUniformityWidget` plots the mean intensity along x and y to
check the illumination, and `QScrollPanel` adds a scroll bar to a panel
of controls when the window is too short for it.

The histogram and the uniformity widget take a screen and watch it, so
they need no connection to the camera.
