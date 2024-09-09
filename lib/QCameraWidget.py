from PyQt5.QtCore import (pyqtProperty, pyqtSlot, QEvent)
from PyQt5.QtWidgets import (QWidget, QPushButton)
from QVideo.lib.QVideoCamera import QVideoCamera
from QVideo.lib.QVideoSource import QVideoSource
from PyQt5 import uic
import sys
from pathlib import Path
import logging
from typing import (Optional, List, Dict, Any)


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


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

    def __init__(self,
                 *args,
                 camera: Optional[QVideoCamera] = None,
                 uiFile: Optional[str] = None,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.camera = camera
        self.ui = self._loadUi(uiFile)
        self._getInterface()
        self._syncProperties()
        self._connectSignals()

    def __del__(self) -> None:
        logger.debug('Deleted')
        if self.camera is not None:
            self.close()

    def closeEvent(self, event: QEvent) -> None:
        logger.debug('Close event')
        self.close()
        event.accept()

    @pyqtProperty(QVideoCamera)
    def camera(self) -> QVideoCamera:
        return self._camera

    @camera.setter
    def camera(self, camera: QVideoCamera) -> None:
        logger.info(f'Setting camera: {type(camera).__name__}')
        self._camera = camera
        if camera is None:
            self._source = None
            return
        self._source = QVideoSource(camera)

    @pyqtProperty(QVideoSource)
    def source(self) -> QVideoSource:
        return self._source

    @source.setter
    def source(self, source: QVideoSource) -> None:
        logger.info(f'Setting source: {type(source.camera).__name__}')
        self._source = source
        self._camera = self._source.camera

    def start(self):
        self.source.start()
        return self

    @pyqtSlot()
    def close(self) -> None:
        logger.debug('Closing')
        self.source.close()
        self.camera = None

    @pyqtProperty(list)
    def properties(self) -> List:
        '''List of camera properties that are controlled by the ui

           This property is configured automatically at instantiation
           and is read-only.
        '''
        return self._properties

    @pyqtProperty(list)
    def methods(self) -> List:
        '''List of camera methods that are called by the ui

           This property is configured automatically at instantiation
           and is read-only.
        '''
        return self._methods

    @pyqtProperty(dict)
    def settings(self) -> Dict:
        '''Dictionary of properties and their current values.

        Setting this property changes values on the UI and on
        the camera.'''
        return {key: self.get(key) for key in self.properties}

    @settings.setter
    def settings(self, settings: Dict) -> None:
        for key, value in settings.items():
            self.set(key, value)

    def get(self, key: str) -> Any:
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

    @pyqtSlot(str, object)
    def set(self, key: str, value: Optional[Any] = None) -> None:
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
        dir = Path(file).parent
        uipath = str(dir / uiFile)
        form, _ = uic.loadUiType(uipath)
        ui = form()
        ui.setupUi(self)
        return ui

    def _getInterface(self):
        properties = self.camera.properties()
        methods = self.camera.methods()
        uiprops = vars(self.ui).keys()
        self._properties = [p for p in properties if p in uiprops]
        self._methods = [m for m in methods if m in uiprops]

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
