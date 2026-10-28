# dvr: recording and playback

`QRecorder` records the frames of a source to a file and `QPlayer` plays a
file back, each on a thread of its own and neither with a window.
`QDVRWidget` is their control panel.  `QCircularBuffer` keeps the most
recent frames in memory.  `QSourceSelector` is a row of radio buttons that
chooses which stream to record (camera, filter pipeline, screen); it
locks while a recording runs.

`formats.py` maps a file extension to a writer and a reader:

| Extension | Writer and reader |
|-----------|-------------------|
| `.h5` | `QHDF5Writer`, `QHDF5Reader`: lossless, timestamps |
| `.avi`, `.mkv`, `.mp4` | `QPyAVWriter` and reader, else OpenCV |

To add a format, subclass `QVideoWriter` and `QVideoReader` (see
`lib/`) and add them to `formats.py`.  The writer runs on its own thread,
so it may take as long as it needs per frame; the recorder reports how far
behind it falls.
