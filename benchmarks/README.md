# benchmarks: measuring how fast QVideo is

`benchmark.py` measures the capture of frames to the interface, the cost of
each filter and the speed of each file writer, and can measure a camera that
is attached.  Its tables are the ones on the Performance page of the
documentation (`docs/performance.rst`); rerun it there when the code, the
machine or the libraries change.

    python benchmarks/benchmark.py                 # capture, filters, record
    python benchmarks/benchmark.py camera -c       # a live camera
    python benchmarks/benchmark.py --csv results   # also save the tables

The directory is not installed with the package.
