Performance
===========

How fast QVideo moves, filters and records frames, measured with a script
that anyone can run.  The numbers belong to one computer and one set of
libraries (below); another machine will give others, so run the script
before you rely on a number.

Reproducing
-----------

``benchmarks/benchmark.py`` in the source tree makes every table of this
page::

    python benchmarks/benchmark.py                  # capture, filters, record
    python benchmarks/benchmark.py capture          # or one of them
    python benchmarks/benchmark.py camera -c        # a camera that is attached
    python benchmarks/benchmark.py --csv results    # also save the tables

It prints the machine first and the tables after, and ``--csv`` saves both.
``camera`` takes the flags of any QVideo program (``-c``, ``-f``, ``-g``)
and measures that camera in place of the synthetic one.

The machine
-----------

.. list-table::
   :widths: 20 80

   * - QVideo
     - 4.17.0
   * - Computer
     - Apple M1 Pro (10 threads)
   * - System
     - Darwin 25.6.0
   * - Python
     - 3.14.10
   * - Qt binding
     - PyQt6 6.11.0
   * - OpenCV, NumPy
     - 5.0.0, 2.5.4
   * - PyAV, h5py
     - 19.0.2, 3.16.0

Capture to the interface
------------------------

A synthetic camera returns a new copy of one frame at a steady rate
(absolute deadlines, so a late frame does not delay the next).  A
:class:`~QVideo.lib.QVideoSource.QVideoSource` reads it in its capture
thread, and a consumer on the GUI thread receives each frame through a
queued connection, as a screen or a recorder does.  *Delay* is the time from
the moment that the camera returned the frame (the ``timestamp`` of its
:class:`~QVideo.lib.videotypes.FrameInfo`) to the moment that the GUI thread
has it.  *CPU* is the processor time of the whole process, as a percentage
of one core.  *Dropped* counts gaps in the frame index.  *Requested* and
*Delivered* are frames per second, *MB* is the size of a frame, and *p50*
and *p99* are the median and the 99th percentile of the delay.  Each row is
three seconds after half a second to settle.

.. csv-table::
   :header: "Frame", "MB", "Requested", "Delivered", "p50 (ms)", "p99 (ms)",
      "CPU (%)", "Dropped"
   :widths: 22 8 11 11 9 9 8 9

   "640x480 gray", "0.29", "30", "29.7", "0.1", "2.22", "1", "0"
   "640x480 gray", "0.29", "100", "100.2", "0.12", "1.59", "2", "0"
   "640x480 gray", "0.29", "300", "300.2", "0.08", "2.52", "5", "0"
   "640x480 gray", "0.29", "1000", "999.4", "0.04", "1.64", "10", "0"
   "1280x1024 gray", "1.25", "30", "30.1", "0.31", "2.93", "2", "0"
   "1280x1024 gray", "1.25", "100", "100.3", "0.14", "1.29", "4", "0"
   "1280x1024 gray", "1.25", "300", "300.2", "0.09", "1.56", "9", "0"
   "1920x1080 color", "5.93", "30", "30.3", "0.12", "1.3", "2", "0"
   "1920x1080 color", "5.93", "60", "60.3", "0.12", "1.75", "3", "0"
   "1920x1080 color", "5.93", "120", "120.2", "0.13", "2.93", "9", "0"

The framework keeps up with every rate that was asked of it, up to 1000
frames a second for small frames and 120 a second for 2-megapixel color
frames, drops nothing, and delivers a frame to the GUI thread in a fraction
of a millisecond (a few milliseconds at the 99th percentile).  The process
uses a few percent of one core for 30 to 100 frames a second.  The synthetic
camera costs almost nothing, so these numbers are the cost of QVideo itself:
a real camera adds its own transfer time, and a program adds what its
slots do.

Cameras that are attached
-------------------------

``benchmarks/benchmark.py camera -g --exposure 1000`` measures an attached
camera in the same way as the synthetic one (``--exposure`` turns off the
automatic exposure, which otherwise lengthens the exposure and lowers the
frame rate in dim light).  Ten seconds each, through the Viva backend:

.. csv-table::
   :header: "Camera", "Frame", "Delivered", "p50 (ms)", "p99 (ms)",
      "CPU (%)", "Dropped"
   :widths: 30 14 11 9 9 8 9

   "Blackfly S BFS-U3-04S2M", "720x540", "199.8", "0.05", "0.32", "9", "0"
   "Blackfly S (1280 x 1024)", "1280x1024", "170.2", "0.04", "0.30", "9", "0"

Each delivers all that the camera produces, and the camera, not QVideo, sets
the rate.  The 1280 x 1024 camera runs at its 170 frames a second.  The
720 x 540 camera reports a throughput of 77.8 MB/s as its maximum
(``DeviceMaxThroughput``), which is 200 frames a second of this size, and
500 frames a second were recorded earlier with the same model, so check the
cable and the port if you see less than you expect.

Also measured on hardware, with other programs:

* A FLIR Blackfly S (USB 3) passes the holographic-trapping test of QHOT in
  the same process as Viva (event-loop median 4.9 ms, 99th percentile
  8.7 ms, 9.8 holograms a second), and Viva holds no interpreter lock.
* A Blackfly S (BFS-U3-04S2M-CS) delivered 500 frames a second at 720 x 540
  through Viva.

The comparison of the Harvesters and Viva backends, with the cost of the
process that keeps the interpreter lock free, is in :doc:`compatibility`
(Known issues).

Filters
-------

The median time of nine calls for one frame, with the default settings of
each filter, on random pixels.  A filter that needs a reference (a dark
frame, a flat field) or a choice (channel gains) passes the frame through
until it has one, and is marked; so is a filter whose default setting
changes nothing (a gamma of 1).  Cropping is free because a crop is a view
of the frame.  A filter with state (a running median) is timed in its
steady state.  A filter whose cost depends on the content of the frame
(blob detection, the circle transform, foreground estimation) will cost
what the content makes it cost.  Some filters are faster on the larger,
color frame than on the smaller, gray one, for reasons that have not been
traced; measure the filters that you use.

.. csv-table::
   :header: "Filter", "720p gray (ms)", "1080p color (ms)", "Note"
   :widths: 30 20 22 30

   "BlobFilter", "3.97", "22.83", ""
   "CartoonFilter", "309.81", "664.43", ""
   "CircleTransformFilter", "21.67", "41.83", ""
   "DarkFrameFilter", "0.0", "0.0", "default settings change nothing"
   "DejitterFilter", "15.91", "38.15", ""
   "DoGFilter", "3.45", "2.87", ""
   "EdgeFilter", "3.25", "7.48", ""
   "ExposureFilter", "0.1", "0.33", ""
   "FlatFieldFilter", "0.0", "0.0", "default settings change nothing"
   "ForegroundEstimator", "5.41", "26.21", ""
   "GammaFilter", "0.1", "0.35", "default settings change nothing"
   "InvertFilter", "0.02", "0.1", ""
   "LaplacianFilter", "1.08", "0.78", ""
   "Median", "0.13", "1.12", ""
   "MoMean", "1.03", "6.95", ""
   "MoMedian", "0.13", "1.12", ""
   "Normalize", "1.44", "11.15", ""
   "PencilSketchFilter", "84.35", "175.16", ""
   "RGBFilter", "0.0", "0.0", "default settings change nothing"
   "ROIFilter", "0.0", "0.0", ""
   "SampleHold", "1.38", "10.07", ""
   "SmoothNormalize", "1.57", "11.2", ""
   "SmoothingFilter", "0.16", "0.62", ""
   "SobelFilter", "3.16", "6.25", ""
   "ThresholdFilter", "0.03", "0.17", ""
   "UnsharpFilter", "0.6", "3.59", ""

At 30 frames a second a program has 33 ms for a frame; the filters that
take more than a few milliseconds belong on a worker thread, which is what
:class:`~QVideo.lib.QFilterPipeline.QFilterPipeline` is for.

Recording
---------

Each writer of :mod:`QVideo.dvr.formats` writes 200 frames of 1280 x 1024
gray, one frame after the other, from memory to a temporary file, and the
time includes closing the file.  *Noise* frames are the worst case for a
lossless codec; *scene* frames are smooth with a little noise, and are
closer to a microscope image.  A live recording has also the camera and the
interface to serve, so leave room.  *Ratio* is the size of the raw frames over
the size of the file; for H.264, which is lossy, it shows what the codec
discarded, not what a lossless one could save.

.. csv-table::
   :header: "Writer", "Frames", "fps", "MB/s", "File (MB)", "Ratio"
   :widths: 30 10 10 10 12 10

   "HDF5; no compression", "noise", "1175.8", "1470", "250.0", "1.0"
   "HDF5; no compression", "scene", "1259.6", "1574", "250.0", "1.0"
   "HDF5; lzf", "noise", "273.6", "342", "250.0", "1.0"
   "HDF5; lzf", "scene", "151.1", "189", "202.8", "1.23"
   "HDF5; zstd", "noise", "1329.9", "1662", "250.0", "1.0"
   "HDF5; zstd", "scene", "665.7", "832", "160.7", "1.56"
   "PyAV FFV1 (lossless)", "noise", "220.1", "275", "265.3", "0.94"
   "PyAV FFV1 (lossless)", "scene", "419.6", "524", "106.1", "2.36"
   "PyAV H.264", "noise", "623.9", "780", "0.8", "295.25"
   "PyAV H.264", "scene", "645.5", "807", "0.3", "948.64"
   "OpenCV (lossless .avi)", "noise", "30.3", "38", "265.4", "0.94"
   "OpenCV (lossless .avi)", "scene", "54.4", "68", "106.0", "2.36"

A recording that must keep every frame should use a lossless format, and
the writer must be faster than the camera: the recorder queues frames while
the writer is behind, and stops the recording if the backlog grows beyond
its limit (see :class:`~QVideo.dvr.QRecorder.QRecorder`).  On this machine
HDF5 with ``zstd`` or no compression writes far faster than a camera
delivers, and keeps a timestamp for every frame.  PyAV with FFV1 is the
fastest lossless video, and the OpenCV writer is several times slower than
PyAV's for the same codec, which is why PyAV is used when it is installed.

What is not measured
--------------------

* The delay from the camera's hardware timestamp to the pixels of the
  screen.  The *Delay* above ends at the GUI thread, not at the display.
* The cost of :class:`~QVideo.lib.QVideoScreen.QVideoScreen` (which depends
  on the window and the graphics system) and of overlays.
* A camera in a process of its own (``QRemoteCamera``): the start of the
  worker, the copy of each frame through shared memory, and the time that a
  setting takes.
* Other computers, Python versions, Qt bindings and operating systems.  A
  result from yours is welcome; send the output of ``--csv``.
