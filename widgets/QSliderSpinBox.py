'''A slider with a spin box, kept in step.

A slider is dragged to find a value and a spin box is typed in to set it
exactly; pyqtgraph has a control of each, and nothing that offers both.
:class:`QSliderSpinBox` is one number with both, and a logarithmic scale for
a range of decades (an exposure time).  It has no camera in it, and nothing
of QVideo.  :mod:`QVideo.lib._sliderspin` makes it a control of a
:class:`~pyqtgraph.parametertree.ParameterTree`, the parameter type
``'sliderspin'``.
'''
from __future__ import annotations

import math
from typing import Any

from qtpy import QtCore, QtWidgets
from pyqtgraph import SpinBox

__all__ = ['QSliderSpinBox']

#: The positions of the slider for a range that is not a few whole steps.
_STEPS = 1000

#: A positive range that spans more than this ratio is logarithmic, unless
#: the caller says otherwise.
_LOG_RATIO = 100.



class QSliderSpinBox(QtWidgets.QWidget):

    '''A slider and a spin box for one number, kept in step.

    Parameters
    ----------
    parent : QWidget, optional
        The parent widget.
    value : float
        The first value.
    minimum, maximum : float
        The range, ``minimum < maximum``.
    integer : bool
        The value is a whole number.
    step : float
        The step of the arrows of the spin box.  A whole number that is
        chosen on the slider is on the grid of this step from *minimum*.
    log : bool or None
        A logarithmic slider.  ``None`` chooses: a range of real numbers that
        is positive and spans more than two decades is logarithmic, and a
        range of whole numbers is linear.
    **spin :
        Options for the spin box: ``suffix``, ``siPrefix``, ``dec``,
        ``decimals``, ``minStep``.

    Signals
    -------
    valueChanged(object)
        The user changed the value: they dragged the slider (at every step of
        the drag), or typed in or stepped the spin box.  Not emitted by
        :meth:`setValue`.
    '''

    valueChanged = QtCore.Signal(object)

    def __init__(self, parent: QtWidgets.QWidget | None = None, *,
                 value: float = 0.,
                 minimum: float = 0.,
                 maximum: float = 1.,
                 integer: bool = False,
                 step: float = 1.,
                 log: bool | None = None,
                 **spin: Any) -> None:
        super().__init__(parent)
        self._busy = False
        self._readOnlyFlag = False
        self._integer = bool(integer)
        self._step = float(step)
        self._log = log
        self._minimum = float(minimum)
        self._maximum = float(maximum)
        self.spin = SpinBox()
        self.spin.setOpts(int=self._integer, step=self._step,
                          bounds=(self._minimum, self._maximum), **spin)
        if self._integer:
            self.spin.setOpts(minStep=1.)
        self.slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.slider.setMinimumWidth(60)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.spin)
        self._setSlider()
        self.setValue(value)
        self.slider.valueChanged.connect(self._sliderMoved)
        self.spin.sigValueChanged.connect(self._spinChanged)

    # ------------------------------------------------------------------
    # The value
    # ------------------------------------------------------------------

    def value(self) -> float | int:
        '''Return the value.'''
        return self.spin.value()

    def setValue(self, value: float) -> None:
        '''Show *value* in both.  Emits nothing.'''
        self._busy = True
        try:
            self.spin.setValue(value)
            self.slider.setValue(self._position(self.spin.value()))
        finally:
            self._busy = False

    # ------------------------------------------------------------------
    # The range and the scale
    # ------------------------------------------------------------------

    @property
    def minimum(self) -> float:
        '''The low end of the range.'''
        return self._minimum

    @property
    def maximum(self) -> float:
        '''The high end of the range.'''
        return self._maximum

    def setRange(self, minimum: float, maximum: float) -> None:
        '''Set the range.  The value is kept, and brought into the range by
        the spin box if it is outside.  Emits nothing.'''
        minimum, maximum = float(minimum), float(maximum)
        if (minimum, maximum) == (self._minimum, self._maximum):
            return
        self._minimum, self._maximum = minimum, maximum
        self._busy = True
        try:
            self.spin.setOpts(bounds=(minimum, maximum))
            self._setSlider()
            self.slider.setValue(self._position(self.spin.value()))
        finally:
            self._busy = False

    def setLogarithmic(self, log: bool | None) -> None:
        '''Choose the scale: ``True``, ``False``, or ``None`` to let the range
        choose.'''
        self._log = log
        self._busy = True
        try:
            self.slider.setValue(self._position(self.spin.value()))
        finally:
            self._busy = False

    def isLogarithmic(self) -> bool:
        '''Return whether the slider is logarithmic.'''
        if self._minimum <= 0. or self._maximum <= self._minimum:
            return False
        if self._log is None:      # whole numbers are on a grid: linear
            return (not self._integer
                    and self._maximum / self._minimum > _LOG_RATIO)
        return bool(self._log)

    def _count(self) -> int:
        '''The number of steps of the slider: one for each whole step of a
        short range of whole numbers, and :data:`_STEPS` otherwise.'''
        if self._integer and not self.isLogarithmic() and self._step > 0:
            whole = round((self._maximum - self._minimum) / self._step)
            return max(1, min(_STEPS, whole))
        return _STEPS

    def _setSlider(self) -> None:
        '''Give the slider as many steps as the range needs.'''
        count = self._count() if self._maximum > self._minimum else 0
        self.slider.setRange(0, count)
        self.slider.setEnabled(count > 0 and not self._readOnlyFlag)

    def _position(self, value: float) -> int:
        '''Return the position of the slider for *value*.'''
        count = self.slider.maximum()
        if count == 0:
            return 0
        value = min(max(value, self._minimum), self._maximum)
        if self.isLogarithmic():
            fraction = (math.log(value / self._minimum)
                        / math.log(self._maximum / self._minimum))
        else:
            fraction = ((value - self._minimum)
                        / (self._maximum - self._minimum))
        return round(count * fraction)

    def _valueAt(self, position: int) -> float:
        '''Return the value for *position* of the slider.'''
        count = self.slider.maximum()
        fraction = position / count if count else 0.
        if self.isLogarithmic():
            value = self._minimum * (self._maximum / self._minimum
                                     ) ** fraction
        else:
            value = self._minimum + (self._maximum - self._minimum) * fraction
        if self._integer:
            if self._step > 1.:
                value = (self._minimum
                         + round((value - self._minimum) / self._step)
                         * self._step)
            value = round(value)
        return min(max(value, self._minimum), self._maximum)

    # ------------------------------------------------------------------
    # The user
    # ------------------------------------------------------------------

    def _sliderMoved(self, position: int) -> None:
        '''The slider moved: the spin box follows.'''
        if self._busy:
            return
        self._busy = True
        try:
            self.spin.setValue(self._valueAt(position))
        finally:
            self._busy = False
        self.valueChanged.emit(self.value())

    def _spinChanged(self, spin: SpinBox) -> None:
        '''The spin box changed: the slider follows.'''
        if self._busy:
            return
        self._busy = True
        try:
            self.slider.setValue(self._position(spin.value()))
        finally:
            self._busy = False
        self.valueChanged.emit(self.value())

    # ------------------------------------------------------------------
    # What a parameter tree asks of a control
    # ------------------------------------------------------------------

    def setOpts(self, **opts: Any) -> None:
        '''Pass options on to the spin box.'''
        if 'step' in opts:
            self._step = float(opts['step'])
        self.spin.setOpts(**opts)
        self._setSlider()

    def setReadOnly(self, readOnly: bool) -> None:
        '''Make the control read only, or not.'''
        self._readOnlyFlag = bool(readOnly)
        self.spin.setReadOnly(readOnly)
        self._setSlider()

    def lineEdit(self) -> QtWidgets.QLineEdit:
        '''The line edit of the spin box.'''
        return self.spin.lineEdit()

    def selectNumber(self) -> None:
        '''Select the number in the spin box, for quick editing.'''
        self.spin.selectNumber()


if __name__ == '__main__':  # pragma: no cover
    import sys

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(
        sys.argv)
    widget = QSliderSpinBox(minimum=1e-5, maximum=30., value=0.01,
                            suffix='s', siPrefix=True)
    widget.valueChanged.connect(print)
    widget.show()
    app.exec()
