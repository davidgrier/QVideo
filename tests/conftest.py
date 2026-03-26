"""pytest configuration: create a QApplication before any test module is imported.

On Ubuntu/xcb, importing pyqtgraph tree-widget classes before a QApplication
exists puts Qt into a state where the subsequent QApplication() call aborts
with SIGABRT.  Creating the application here (the first thing pytest runs)
guarantees every test module sees an existing instance via
QApplication.instance() and never calls the constructor a second time.
"""
import sys
from pyqtgraph.Qt import QtWidgets

_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv[:1])
