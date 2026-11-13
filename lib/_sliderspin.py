'''The ``'sliderspin'`` control of a pyqtgraph parameter tree.

pyqtgraph's ``float`` control is a spin box and its ``slider`` control is a
slider with a label; :class:`~QVideo.widgets.QSliderSpinBox.QSliderSpinBox` is
both, and this module makes it a control that a description of a
:class:`~pyqtgraph.parametertree.ParameterTree` may ask for::

    {'name': 'ExposureTime', 'type': 'sliderspin', 'value': 0.01,
     'limits': (1e-5, 30.), 'units': 's', 'siPrefix': True}

Importing the module registers the type.  The widget is imported when the
first control is made, not here, because the package of the widgets imports
:mod:`QVideo.lib`, which imports this module.
'''
from __future__ import annotations

from typing import Any

import qtpy  # noqa: F401  chooses the binding before pyqtgraph can
from pyqtgraph.parametertree import Parameter, registerParameterType
from pyqtgraph.parametertree.parameterTypes.numeric import NumericParameterItem

__all__ = ['SliderSpinParameter', 'SliderSpinParameterItem']

#: The options of the spin box that a parameter passes on to it.
_SPIN_OPTIONS = ('suffix', 'siPrefix', 'step', 'dec', 'decimals', 'minStep')


class SliderSpinParameterItem(NumericParameterItem):

    '''The control of a ``'sliderspin'`` parameter: a
    :class:`QSliderSpinBox`.  It takes the options of the ``'float'`` and
    ``'int'`` controls of pyqtgraph (``limits`` or ``min`` and ``max``,
    ``step``, ``units``, ``siPrefix``, ``decimals``, ``dec``) and the options
    ``int`` (whole numbers) and ``log`` (a logarithmic slider, or ``None`` to
    let the range choose).'''

    def __init__(self, param: Parameter, depth: int) -> None:
        super().__init__(param, depth)
        # A slider that shows up only when its row is clicked is of no use:
        # keep the control visible, as a slider is (pyqtgraph hides the
        # editors of numbers until the row is selected).
        self.hideWidget = False

    def makeWidget(self) -> Any:
        from QVideo.widgets.QSliderSpinBox import QSliderSpinBox
        opts = self.param.opts
        limits = opts.get('limits')
        low, high = (limits if limits is not None
                     else (opts.get('min', 0.), opts.get('max', 1.)))
        spin = {key: opts[key] for key in _SPIN_OPTIONS
                if key in opts and key != 'step'}
        if 'units' in opts and 'suffix' not in opts:
            spin['suffix'] = opts['units']
        widget = QSliderSpinBox(
            minimum=low, maximum=high, integer=bool(opts.get('int', False)),
            step=opts.get('step', 1.), log=opts.get('log'),
            value=opts.get('value', low), **spin)
        # what a pyqtgraph control must have: the signal of a change
        widget.sigChanged = (  # pyright: ignore[reportAttributeAccessIssue]
            widget.valueChanged)
        return widget

    def limitsChanged(self, param: Parameter, limits: Any) -> None:
        self.widget.setRange(*limits)

    def optsChanged(self, param: Parameter, opts: dict) -> None:
        # not NumericParameterItem's: that one passes options to a SpinBox
        super(NumericParameterItem, self).optsChanged(param, opts)
        spin = {key: opts[key] for key in _SPIN_OPTIONS
                if opts.get(key) is not None}
        if 'units' in opts and 'suffix' not in opts:
            spin['suffix'] = opts['units']
        if spin:
            self.widget.setOpts(**spin)
        if 'log' in opts:
            self.widget.setLogarithmic(opts['log'])
        if 'min' in opts or 'max' in opts:
            self.widget.setRange(opts.get('min', self.widget.minimum),
                                 opts.get('max', self.widget.maximum))
        self.updateDisplayLabel()


class SliderSpinParameter(Parameter):

    '''A number, shown as a slider with a spin box (parameter type
    ``'sliderspin'``).  The option ``int`` makes it a whole number.'''

    itemClass = SliderSpinParameterItem  # pyright: ignore[reportAssignmentType]

    def _interpretValue(self, v: Any) -> float | int:
        if self.opts.get('int'):
            return int(round(v))
        return float(v)


registerParameterType('sliderspin', SliderSpinParameter, override=True)
