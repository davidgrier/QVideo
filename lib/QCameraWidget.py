from PyQt5.QtCore import (QThread, pyqtProperty, pyqtSlot)
from PyQt5.QtWidgets import (QWidget, QPushButton)
from QVideo.lib.QVideoCamera import QVideoCamera
from PyQt5 import uic
import sys
import os
import logging


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class QCameraWidget(QWidget):
    '''Glue class that binds a QVideoCamera to a UI that
    controls its attributes

    '''

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

    def __del__(self):
        logger.debug('Deleted')
        if self.camera is not None:
            self.close()

    def closeEvent(self, event):
        logger.debug('Close event')
        self.close()
        event.accept()

    @pyqtProperty(QVideoCamera)
    def camera(self):
        return self._camera

    @camera.setter
    def camera(self, camera):
        logger.info(f'Setting camera: {type(camera).__name__}')
        self._camera = camera
        if camera is None:
            return
        self.thread = QThread()
        camera.moveToThread(self.thread)
        self.thread.started.connect(camera.start)
        self.thread.finished.connect(camera.close)
        self.thread.start(QThread.TimeCriticalPriority)

    def close(self):
        logger.debug('Closing')
        self.thread.quit()
        self.thread.wait()
        self.camera = None

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
                logger.debug(f'Requesting {key}: Obtained {value}')
                self.blockSignals(True)
            try:
                logger.debug(f'Setting {key} to {value}')
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
        self._properties = [p for p in self.camera.properties()
                            if p in uiprops]
        self._methods = [m for m in self.camera.methods() if m in uiprops]

    def _syncProperties(self):
        for prop in self.properties:
            self.set(prop)

    def _connectSignals(self):
        for prop in self.properties:
            widget = getattr(self.ui, prop)
            signal = self._wmethod(widget, self.wsignal)
            if signal is not None:
                logger.debug(f'Connecting property {prop}')
                signal.connect(self._setCameraProperty)
        for method in self.methods:
            logger.debug(f'Connecting method {method}')
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
            logger.debug(f'Setting camera property: {name}: {value}')
            setattr(self.camera, name, value)
        else:
            logger.warning(f'Failed to set {name} ({value}): unknown')
