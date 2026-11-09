'''The camera properties that a web page may show and change.

:class:`~QVideo.lib.QWebScreen.QWebScreen` sends the page a description of
the properties that it exposes, built from the
:class:`~QVideo.lib.QCamera.PropertySpec` of the camera, and checks every
value that the page sends back.  This module holds both, with no Qt and no
server, so that what a browser may do to a camera is in one short place.

A page is not trusted: it can send anything.  :func:`coerce` is the gate.  A
number is clipped to the limits of the property, a choice must be one of the
listed values, and a property that the application did not expose, or that
the camera cannot write, cannot be set.
'''
from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from typing import Any

from QVideo.lib.QCamera import PropertySpec

__all__ = ['COMMON', 'choose', 'describe', 'coerce']

#: The properties that are exposed when the application names none: the
#: usual ones of a camera, by lowercase name.  A backend that spells them
#: otherwise, or an application that wants more, names them.  ``resolution``
#: is among them (a change reshapes the frames of a recording in progress,
#: as it does in the window); ``width`` and ``height`` are not.
COMMON = ('exposure', 'exposuretime', 'gain', 'gamma', 'brightness',
          'contrast', 'saturation', 'blacklevel', 'whitelevel', 'fps',
          'acquisitionframerate', 'color', 'mirrored', 'flipped',
          'resolution')

_KINDS = {bool: 'bool', int: 'int', float: 'float'}


def kind(spec: PropertySpec) -> str | None:
    '''Return how a page shows *spec*: ``'bool'``, ``'int'``, ``'float'`` or
    ``'list'``; ``None`` for a property that a page cannot show.'''
    if spec.ptype is str:
        return 'list' if spec.limits else None
    return _KINDS.get(spec.ptype)


def choose(properties: dict[str, PropertySpec],
           names: Sequence[str] | None = None) -> list[str]:
    '''Return the names of the properties to expose.

    Parameters
    ----------
    properties : dict
        The ``properties`` of the camera.
    names : sequence of str, optional
        What the application asked for; unknown names, and properties that a
        page cannot show, are left out.  ``None`` takes those of
        :data:`COMMON` that the camera has, lets us write and does not hide:
        a camera hides a property that it changes only together with
        another (the frame rate of an OpenCV camera, which follows the
        resolution) and that the window of the instrument does not show
        either.
    '''
    if names is None:
        names = [name for name, spec in properties.items()
                 if name.lower() in COMMON and spec.setter is not None
                 and not spec.hidden]
    return [name for name in names
            if name in properties and kind(properties[name]) is not None]


def describe(properties: dict[str, PropertySpec], names: Iterable[str],
             values: dict[str, Any]) -> list[dict[str, Any]]:
    '''Return what a page needs to build a control for each property.

    Only plain values (strings, numbers, booleans, lists), so the result is
    JSON.  An entry has ``name``, ``type`` (``'bool'``, ``'int'``,
    ``'float'`` or ``'list'``), ``value`` and ``writable``; a number adds
    ``min``, ``max`` and ``step`` where the camera gives them, and a list
    adds ``limits``.  A property with no value just now is left out.
    '''
    entries = []
    for name in names:
        spec = properties[name]
        value = values.get(name)
        if value is None:
            continue
        entry: dict[str, Any] = dict(name=name, type=kind(spec),
                                     value=value,
                                     writable=spec.setter is not None)
        entry.update({key: attribute for key, attribute in
                      (('min', spec.minimum), ('max', spec.maximum),
                       ('step', spec.step)) if attribute is not None})
        if spec.limits:
            entry['limits'] = list(spec.limits)
        entries.append(entry)
    return entries


def coerce(spec: PropertySpec, value: Any) -> Any:
    '''Return *value* as the property takes it, or raise ``ValueError``.

    A number is clipped to ``minimum`` and ``maximum`` (an integer is
    rounded), a choice must be one of ``limits``, and a boolean must be one.
    Anything else, such as a string for a number or ``NaN``, is refused.
    '''
    which = kind(spec)
    if which == 'bool':
        if not isinstance(value, bool):
            raise ValueError(f'{value!r} is not a boolean')
        return value
    if which == 'list':
        if value not in (spec.limits or ()):
            raise ValueError(f'{value!r} is not one of the choices')
        return value
    if which in ('int', 'float'):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f'{value!r} is not a number')
        if not math.isfinite(value):
            raise ValueError(f'{value!r} is not finite')
        if spec.minimum is not None:
            value = max(value, spec.minimum)
        if spec.maximum is not None:
            value = min(value, spec.maximum)
        return round(value) if which == 'int' else float(value)
    raise ValueError('this property cannot be set from a page')
