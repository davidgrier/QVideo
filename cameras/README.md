# cameras: one directory per kind of camera

Each subdirectory is a backend: `Q<Name>Camera` talks to the hardware,
`Q<Name>Source` runs it in a thread and `Q<Name>Tree` builds its controls.
Backends that use a vendor SDK import it inside `try/except`, so QVideo
imports without it.

| Directory | Cameras |
|-----------|---------|
| `Noise` | none: random frames, the reference for writing a backend |
| `OpenCV` | webcams and video files |
| `Genicam` | any GenICam camera, through Harvesters and a GenTL producer |
| `Flir`, `Basler`, `IDS`, `MV`, `Vimbax` | `Genicam` with a vendor producer |
| `Picamera` | Raspberry Pi camera modules, including the AI camera |

`chooser.py` is where a camera is chosen: the table of backends (with the
flag of each), the code that opens a camera from it, which `Camera()` and
the command-line chooser share, and the chooser that turns the flags of a
command line into an open camera and its controls.  `gentl.py` diagnoses
GenTL problems (`python -m QVideo.cameras.gentl`).

To add a camera, read `docs/backends.rst` ("Writing a camera backend").
A backend is accepted when it passes the conformance suite
(`tests/conformance.py`) on a simulated device.
