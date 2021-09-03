from PyQt5.QtCore import (QThread, pyqtProperty, pyqtSlot)
from PyQt5.QtWidgets import (QWidget, QPushButton)
from QVideoCamera import QVideoCamera
from PyQt5 import uic
import types
import sys
import os
import logging


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


class QCameraWidget(QWidget):

    wsetter = {'QCheckBox':      'setChecked',
               'QComboBox':      'setCurrentIndex',
               'QDoubleSpinBox': 'setValue',
               'QGroupBox':      'setChecked',
               'QLabel':         'setText',
               'QLineEdit':      'setText',
               'QPushButton':    'setChecked',
               'QRadioButton':   'setChecked',
               'QSpinBox':       'setValue'}

    wgetter = {'QCheckBox':      'isChecked',
               'QComboBox':      'currentIndex',
               'QDoubleSpinBox': 'value',
               'QGroupBox':      'isChecked',
               'QLabel':         'text',
               'QLineEdit':      'text',
               'QPushButton':    'isChecked',
               'QRadioButton':   'isChecked',
               'QSpinBox':       'value'}

    wsignal = {'QCheckBox':      'toggled',
               'QComboBox':      'currentIndexChanged',
               'QDoubleSpinBox': 'valueChanged',
               'QGroupBox':      'toggled',
               'QLineEdit':      'editingFinished',
               'QPushButton':    'toggled',
               'QRadioButton':   'toggled',
               'QSpinBox':       'valueChanged'}

    def __init__(self, *args, camera=None, uiFile=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.camera = camera
        self.ui = self._loadUi(uiFile)
        self._identifyProperties()
        self._syncProperties()
        self._connectSignals()

    @pyqtProperty(QVideoCamera)
    def camera(self):
        return self._camera

    @camera.setter
    def camera(self, camera):
        logger.debug(f'Setting camera: {type(camera)}')
        self._camera = camera
        if camera is None:
            return
        self.thread = QThread()
        camera.moveToThread(self.thread)
        self.thread.started.connect(camera.run)
        camera.finished.connect(self.thread.quit)
        camera.finished.connect(self.camera.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start(QThread.TimeCriticalPriority)

    def closeEvent(self, event):
        self.camera.stop()
        self.thread.quit()
        self.thread.wait()
        event.accept()

    @pyqtProperty(list)
    def properties(self):
        '''List of camera properties that are controlled by the ui

           This property is configured automatically at instantiation
           and is read-only.
        '''
        return self._properties

    @pyqtProperty(list)
    def methods(self):
        '''List of camera methods that are called by the ui

           This property is configured automatically at instantiation
           and is read-only.
        '''
        return self._methods

    @pyqtProperty(dict)
    def settings(self):
        '''Dictionary of properties and their current values.

        Setting this property changes values on the UI and on
        the camera.'''
        return {key: self.get(key) for key in self.properties}

    @settings.setter
    def settings(self, settings):
        for key, value in settings.items():
            self.set(key, value)

    def get(self, key):
        '''Get value of named widget

        Arguments
        ---------
        key: str
            Name of property to retrieve
        '''
        if hasattr(self.ui, key):
            widget = getattr(self.ui, key)
            getter = self._wmethod(widget, self.wgetter)
            return getter()
        logger.error(f'Unknown property {key}')
        return None

    def set(self, key, value=None):
        '''Set value of named property

        This method explicitly sets the value of the named
        widget in the UI and relies on the widget to emit a
        signal that will set the corresponding camera value.

        If no value is provided, the method set the widget
        to the value obtained from the camera.

        Arguments
        ---------
        key: str
            Name of property
        value: bool | int | float | str [optional]
            Value of property
            Default: update widget value with camera value

        Note
        ----

        '''
        if hasattr(self.ui, key):
            widget = getattr(self.ui, key)
            setter = self._wmethod(widget, self.wsetter)
            if value is None:
                value = getattr(self.camera, key, None)
                self.blockSignals(True)
            try:
                setter(value)
            except Exception as ex:
                logger.error(f'Could not set {key} to {value}: {ex}')
            self.blockSignals(False)
        else:
            logger.error(f'Unknown property {key}')

    def _wmethod(self, widget, method):
        typeName = type(widget).__name__.split('.')[-1]
        if typeName in method:
             return getattr(widget, method[typeName])
        return None

    def _loadUi(self, uiFile):
        file = sys.modules[self.__module__].__file__
        dir = os.path.dirname(os.path.abspath(file))
        uipath = os.path.join(dir, uiFile)
        form, _ = uic.loadUiType(uipath)
        ui = form()
        ui.setupUi(self)
        return ui

    def _identifyProperties(self):
        uiprops = vars(self.ui).keys()
        self._properties = []
        self._methods = []
        for k, v in vars(type(self.camera)).items():
            if k not in uiprops:
                continue
            if isinstance(v, pyqtProperty):
                self._properties.append(k)
            elif isinstance(v, types.FunctionType):
                self._methods.append(k)

    def _syncProperties(self):
        for prop in self.properties:
            self.set(prop)

    def _connectSignals(self):
        for prop in self.properties:
            widget = getattr(self.ui, prop)
            signal = self._wmethod(widget, self.wsignal)
            if signal is not None:
                signal.connect(self._setCameraProperty)
        for method in self.methods:
            widget = getattr(self.ui, method)
            if isinstance(widget, QPushButton):
                widget.clicked.connect(getattr(self.camera, method))

    @pyqtSlot(bool)
    @pyqtSlot(int)
    @pyqtSlot(float)
    @pyqtSlot(str)
    def _setCameraProperty(self, value):
        name = self.sender().objectName()
        if hasattr(self.camera, name):
            setattr(self.camera, name, value)
            logger.debug(f'Setting camera: {name}: {value}')
