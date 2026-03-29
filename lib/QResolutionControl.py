'''Stop-transparent resolution and frame-rate control widget.'''
import numpy as np
from pyqtgraph.Qt import QtCore, QtWidgets
from QVideo.lib.QVideoSource import QVideoSource


__all__ = ['QResolutionControl']


class QResolutionControl(QtWidgets.QWidget):

    '''Stop-transparent resolution and frame-rate control for a
    :class:`~QVideo.lib.QVideoSource.QVideoSource`.

    Displays **Width**, **Height**, and (optionally) **FPS** spinboxes
    alongside a read-only *Resulting fps* label.  Clicking **Apply**:

    1. Stops the source (if running) and waits for the thread to finish.
    2. Writes the requested width, height, and fps to the camera via
       :meth:`~QVideo.lib.QCamera.QCamera.set` (skips any read-only
       property).
    3. Restarts the source.
    4. Re-enables controls and updates the result label once the first
       frame arrives.
    5. Emits :attr:`changed` with the actual values read back from the
       camera.

    An optional enumerated resolution dropdown — populated from a
    caller-supplied list — populates the Width/Height spinboxes on
    selection and is deselected when the spinboxes are edited manually.

    This widget is backend-agnostic: it works with any camera that
    registers ``width`` and ``height`` as writable properties (e.g.
    GenICam cameras).  OpenCV cameras register those properties as
    read-only and are configured at construction time instead; see
    :class:`~QVideo.cameras.OpenCV.QOpenCVCamera` and
    :func:`~QVideo.lib.resolutions.configure`.

    Parameters
    ----------
    source : QVideoSource
        The video source to control.
    resolutions : list[tuple[int, int]] or None
        Optional list of ``(width, height)`` pairs for the resolution
        dropdown.  ``None`` (default) omits the dropdown.
    *args :
        Forwarded to :class:`~PyQt5.QtWidgets.QWidget`.
    **kwargs :
        Forwarded to :class:`~PyQt5.QtWidgets.QWidget`.

    Signals
    -------
    changed(int, int, object)
        Emitted after a successful restart with the actual
        ``(width, height, fps)`` read back from the camera.
        *fps* is ``None`` if the camera does not expose an fps property.
    '''

    changed = QtCore.pyqtSignal(int, int, object)

    def __init__(self, source: QVideoSource, *args,
                 resolutions: list[tuple[int, int]] | None = None,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._source = source
        self._resolutions = resolutions or []
        self._resolutionMap = {
            f'{w}\u00d7{h}': (w, h) for w, h in self._resolutions
        }
        self._setupUi()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def source(self) -> QVideoSource:
        '''The video source being controlled.'''
        return self._source

    @property
    def camera(self):
        '''The underlying camera (``QVideoSource.source``).'''
        return self._source.source

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setupUi(self) -> None:
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        if self._resolutions:
            layout.addWidget(QtWidgets.QLabel('Resolution:'))
            self._resolutionCombo = QtWidgets.QComboBox()
            for w, h in self._resolutions:
                self._resolutionCombo.addItem(f'{w}\u00d7{h}')
            self._matchDropdown()
            self._resolutionCombo.currentTextChanged.connect(
                self._onDropdownChanged)
            layout.addWidget(self._resolutionCombo)
        else:
            self._resolutionCombo = None

        layout.addWidget(QtWidgets.QLabel('W:'))
        self._widthSpin = QtWidgets.QSpinBox()
        self._widthSpin.setRange(1, 99999)
        self._widthSpin.setValue(self._readWidth())
        self._widthSpin.valueChanged.connect(self._onSpinChanged)
        layout.addWidget(self._widthSpin)

        layout.addWidget(QtWidgets.QLabel('H:'))
        self._heightSpin = QtWidgets.QSpinBox()
        self._heightSpin.setRange(1, 99999)
        self._heightSpin.setValue(self._readHeight())
        self._heightSpin.valueChanged.connect(self._onSpinChanged)
        layout.addWidget(self._heightSpin)

        if 'fps' in self.camera._properties:
            layout.addWidget(QtWidgets.QLabel('FPS:'))
            self._fpsSpin = QtWidgets.QDoubleSpinBox()
            self._fpsSpin.setRange(0.1, 10000.)
            self._fpsSpin.setDecimals(1)
            self._fpsSpin.setValue(float(self.camera.get('fps')))
            layout.addWidget(self._fpsSpin)
        else:
            self._fpsSpin = None

        self._resultLabel = QtWidgets.QLabel()
        self._updateResultLabel()
        layout.addWidget(self._resultLabel)

        self._applyBtn = QtWidgets.QPushButton('Apply')
        self._applyBtn.clicked.connect(self.apply)
        layout.addWidget(self._applyBtn)

        layout.addStretch()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _readWidth(self) -> int:
        if 'width' in self.camera._properties:
            return int(self.camera.get('width'))
        return 640

    def _readHeight(self) -> int:
        if 'height' in self.camera._properties:
            return int(self.camera.get('height'))
        return 480

    def _isWritable(self, name: str) -> bool:
        '''Return ``True`` if *name* is a registered writable property.'''
        spec = self.camera._properties.get(name)
        return spec is not None and spec.get('setter') is not None

    def _matchDropdown(self) -> None:
        '''Sync the dropdown to the current camera resolution silently.'''
        if self._resolutionCombo is None:
            return
        res_str = f'{self._readWidth()}\u00d7{self._readHeight()}'
        idx = self._resolutionCombo.findText(res_str)
        with QtCore.QSignalBlocker(self._resolutionCombo):
            self._resolutionCombo.setCurrentIndex(idx)

    def _updateResultLabel(self) -> None:
        if 'fps' in self.camera._properties:
            fps = float(self.camera.get('fps'))
            self._resultLabel.setText(f'({fps:.1f} fps)')
        else:
            self._resultLabel.setText('')

    def _setControlsEnabled(self, enabled: bool) -> None:
        for widget in (self._resolutionCombo, self._widthSpin,
                       self._heightSpin, self._fpsSpin, self._applyBtn):
            if widget is not None:
                widget.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @QtCore.pyqtSlot(str)
    def _onDropdownChanged(self, text: str) -> None:
        if text not in self._resolutionMap:
            return
        w, h = self._resolutionMap[text]
        with QtCore.QSignalBlocker(self._widthSpin), \
                QtCore.QSignalBlocker(self._heightSpin):
            self._widthSpin.setValue(w)
            self._heightSpin.setValue(h)

    @QtCore.pyqtSlot()
    def _onSpinChanged(self) -> None:
        '''Keep the dropdown in sync when spinboxes are edited manually.'''
        if self._resolutionCombo is None:
            return
        res_str = (f'{self._widthSpin.value()}'
                   f'\u00d7{self._heightSpin.value()}')
        idx = self._resolutionCombo.findText(res_str)
        with QtCore.QSignalBlocker(self._resolutionCombo):
            self._resolutionCombo.setCurrentIndex(idx)   # -1 clears selection

    @QtCore.pyqtSlot()
    def apply(self) -> None:
        '''Stop the source, apply settings, and restart.

        Disables all controls and shows ``Restarting…`` in the result
        label while the stop/restart cycle runs.  Re-enables controls
        once the first new frame arrives.
        '''
        width = self._widthSpin.value()
        height = self._heightSpin.value()
        fps = float(self._fpsSpin.value()) if self._fpsSpin is not None else None

        self._setControlsEnabled(False)
        self._resultLabel.setText('Restarting\u2026')
        QtWidgets.QApplication.processEvents()

        was_running = self._source.isRunning()
        if was_running:
            self._source.stop()
            self._source.wait()

        if self._isWritable('width'):
            self.camera.set('width', width)
        if self._isWritable('height'):
            self.camera.set('height', height)
        if fps is not None and self._isWritable('fps'):
            self.camera.set('fps', fps)

        if was_running:
            self._source.newFrame.connect(self._onFirstFrame)
            self._source.start()
        else:
            self._finalize()

    @QtCore.pyqtSlot(np.ndarray)
    def _onFirstFrame(self, _frame: np.ndarray) -> None:
        self._source.newFrame.disconnect(self._onFirstFrame)
        self._finalize()

    def _finalize(self) -> None:
        '''Update UI with hardware-actual values and emit :attr:`changed`.'''
        width = self._readWidth()
        height = self._readHeight()
        fps = (float(self.camera.get('fps'))
               if 'fps' in self.camera._properties else None)

        with QtCore.QSignalBlocker(self._widthSpin), \
                QtCore.QSignalBlocker(self._heightSpin):
            self._widthSpin.setValue(width)
            self._heightSpin.setValue(height)

        if self._fpsSpin is not None and fps is not None:
            with QtCore.QSignalBlocker(self._fpsSpin):
                self._fpsSpin.setValue(fps)

        self._matchDropdown()
        self._updateResultLabel()
        self._setControlsEnabled(True)
        self.changed.emit(width, height, fps)

    @classmethod
    def example(cls) -> None:  # pragma: no cover
        '''Demonstrate the control with a noise camera source.'''
        import pyqtgraph as pg
        from QVideo.cameras.Noise import QNoiseSource
        from QVideo.lib.resolutions import COMMON_RESOLUTIONS

        pg.mkQApp('QResolutionControl Example')

        source = QNoiseSource().start()

        window = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(window)

        status = QtWidgets.QLabel()
        resolutions = [(w, h) for w, h in COMMON_RESOLUTIONS
                       if w <= source.source.width * 2]
        ctrl = cls(source, resolutions=resolutions)
        ctrl.changed.connect(
            lambda w, h, fps: status.setText(
                f'Applied: {w}\u00d7{h}'
                + (f' @ {fps:.1f} fps' if fps is not None else '')))

        layout.addWidget(ctrl)
        layout.addWidget(status)
        window.setWindowTitle('QResolutionControl Example')
        window.show()
        pg.exec()


if __name__ == '__main__':  # pragma: no cover
    QResolutionControl.example()
