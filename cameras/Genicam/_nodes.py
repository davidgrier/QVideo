'''The nodes of a GenICam node map, as the rest of QVideo sees them.

Harvesters hands over the node map as Python objects of the ``genicam``
binding: a category, a command, or a node that holds a value of one of six
types.  This module is the one place that knows those types.  The camera
(:class:`~QVideo.cameras.Genicam.QGenicamCamera`) and its tree ask it what
a node is (:func:`nodeKind`), what bounds it (:func:`limits`), how to read
and write it (:func:`read`, :func:`write`), and for plain data about it
(:func:`spec`, :func:`describe`, :func:`snapshot`).  None of them holds the
lock of the camera, and the camera must: **the caller holds the camera
lock** for every function here that touches a node, because the binding
keeps the interpreter lock while it waits for the lock of the node map.

To teach the camera a new type of node, add it to ``VALUE_KINDS`` and to
:func:`limits`, :func:`read` and :func:`write`.  In Spinnaker's binding an
enumeration is also an integer, so ``VALUE_KINDS`` lists it first.

The binding is imported here, so that this module needs ``genicam`` and
nothing else; :mod:`~QVideo.cameras.Genicam._camera` imports it after its
own, friendlier check for the library.
'''
import logging

import numpy as np
from genicam.genapi import (IValue, EAccessMode, ICategory, ICommand,
                            IEnumeration, IBoolean, IInteger, IFloat,
                            IString, IRegister)

from QVideo.lib import QCamera


logger = logging.getLogger(__name__)

#: The kinds of node that hold a value, in the order to test them, with the
#: Python type of the property that each becomes.  An enumeration comes
#: first: in Spinnaker's binding it is also an integer.
VALUE_KINDS = (('enum', IEnumeration, str), ('bool', IBoolean, bool),
               ('int', IInteger, int), ('float', IFloat, float),
               ('str', IString, str), ('register', IRegister, str))

#: The Python type of the property for each kind of node that holds a value.
PTYPES = {kind: ptype for kind, _, ptype in VALUE_KINDS}

#: The kinds of node that a snapshot names; every other kind is ``'other'``.
STATE_KINDS = frozenset({'enum', 'int', 'float', 'register'})

#: Registers longer than this many bytes are reported by size, not content.
MAX_REGISTER_BYTES = 256


def registerText(feature: IRegister) -> str:
    '''Return the bytes of a register node as hexadecimal text.

    A register is a raw block of the camera's memory.  Short registers
    read as ``'0a 1b ...'``; long ones (lookup tables, firmware) as
    ``'<4096 bytes>'``, which avoids reading them.
    '''
    length = feature.length
    if length > MAX_REGISTER_BYTES:
        return f'<{length} bytes>'
    return bytes(feature.get(length)).hex(' ')


def nodeKind(feature: IValue) -> str:
    '''Return the kind of node that *feature* is.

    ``'group'`` is a category and ``'action'`` a command.  A node that holds
    a value is ``'enum'``, ``'bool'``, ``'int'``, ``'float'``, ``'str'`` or
    ``'register'``.  Anything else is ``'other'``.
    '''
    if isinstance(feature, ICategory):
        return 'group'
    if isinstance(feature, ICommand):
        return 'action'
    for kind, node_type, _ in VALUE_KINDS:
        if isinstance(feature, node_type):
            return kind
    return 'other'


def limits(feature: IValue, kind: str) -> dict[str, object]:
    '''Return what bounds a node of the given *kind*.

    An enumeration has ``entries``, the names of its values.  A number
    has ``min``, ``max`` and ``inc``, which is ``None`` if the node has
    no increment.  Any other node has no limits.
    '''
    if kind == 'enum':
        return {'entries': [v.symbolic for v in feature.entries]}
    if kind == 'int':
        return {'min': feature.min, 'max': feature.max, 'inc': feature.inc}
    if kind == 'float':
        return {'min': feature.min, 'max': feature.max,
                'inc': feature.inc if feature.has_inc() else None}
    return {}


def read(feature: IValue, kind: str) -> object:
    '''Read the value of a node of the given *kind*.'''
    if kind == 'enum':
        return feature.to_string()
    if kind == 'register':
        return registerText(feature)
    return feature.value


def write(feature: IValue, value: QCamera.PropertyValue) -> None:
    '''Set the value of a node, within its limits.

    A value outside the range of a number is clipped to it, an integer is
    snapped to the increment, and an enumeration refuses a name that it
    does not have (with a warning).
    '''
    logger.debug(f'Setting {feature.node.name}: {value}')
    kind = nodeKind(feature)
    if kind == 'enum':
        if value in limits(feature, kind)['entries']:
            feature.from_string(value)
        else:
            logger.warning(f'{value} is not in {feature.node.name}')
    elif kind == 'bool':
        feature.value = bool(value)
    elif kind == 'int':
        lo, hi, inc = feature.min, feature.max, feature.inc
        value = int(np.clip(value, lo, hi))
        steps = round((value - lo) / inc)
        feature.value = int(np.clip(steps * inc + lo, lo, hi))
    elif kind == 'float':
        feature.value = float(np.clip(value, feature.min, feature.max))
    elif kind == 'str':
        feature.value = str(value)


def spec(feature: IValue, kind: str) -> tuple[type, dict[str, object]]:
    '''Return the Python type and registerProperty metadata of a node.'''
    bounds = limits(feature, kind)
    if kind == 'enum':
        return str, {'limits': bounds['entries']}
    meta = {}
    if bounds:
        meta = {'minimum': bounds['min'], 'maximum': bounds['max']}
        if bounds['inc'] is not None:
            meta['step'] = bounds['inc']
    if kind == 'float' and getattr(feature, 'unit', None):
        meta['unit'] = feature.unit
    return PTYPES[kind], meta


def describe(feature: IValue) -> dict:
    '''Return the description of *feature* and of what it contains.

    Only plain values (numbers, strings, lists, dicts), so the result
    crosses the process boundary of a
    :class:`~QVideo.lib.remote.camera.QRemoteCamera`.  Every entry has
    ``name``, ``title`` and ``visibility`` (an integer); a category adds
    ``type='group'`` and ``children``; a leaf adds ``type``, ``value``,
    ``default`` and the limits of its type.  A float adds ``unit`` and, if
    the node has an increment, ``step``.
    '''
    this = dict(name=feature.node.name,
                title=feature.node.display_name,
                visibility=int(feature.node.visibility))
    mode = feature.node.get_access_mode()
    kind = nodeKind(feature)
    if mode == EAccessMode.NI:
        pass
    elif kind == 'group':
        this['type'] = 'group'
        this['children'] = [describe(f) for f in feature.features]
    elif kind == 'action':
        this['type'] = 'action'
    elif mode in (EAccessMode.RW, EAccessMode.RO):
        if kind in PTYPES:
            this.update(_describeValue(feature, kind))
        else:
            logger.debug(f'Unsupported node type: {feature.node.name}: '
                         f'{type(feature)}')
    return this


def _describeValue(feature: IValue, kind: str) -> dict:
    '''Describe a readable node that holds a value.'''
    value = read(feature, kind)
    this = dict(type='list' if kind == 'enum' else PTYPES[kind].__name__,
                value=value, default=value)
    bounds = limits(feature, kind)
    if kind == 'enum':
        this['limits'] = bounds['entries']
    elif bounds:
        this.update(min=bounds['min'], max=bounds['max'])
        if bounds['inc'] is not None:
            this['step'] = bounds['inc']
    if kind == 'float':
        this['unit'] = feature.unit
    elif kind == 'register':
        # A register is a raw block of the camera's memory: show its
        # bytes as read-only text.
        this['readonly'] = True
    return this


def selfChanging(nodeMap) -> frozenset[str] | None:
    '''Return the names of the nodes that can change without a write.

    A camera tells the node map which nodes it changes by itself (the
    exposure while it is automatic, the temperature, a frame rate that
    depends on the exposure) by giving them a ``PollingTime``, and every
    node that depends on one of them (``pDependent``) can change with it.
    A node that is not among them changes only when something writes it.

    Returns ``None`` if the node map names no polled node, or if it cannot
    be read: the caller then has no reason to leave any node out.  The scan
    reads every node of the map (35 ms for 3,000 nodes), so it is done once.
    '''
    names: set[str] = set()
    try:
        for feature in nodeMap.nodes:
            node = feature.node
            if node.polling_time > 0 and 'pDependent' in node.property_names:
                names.update(node.get_property('pDependent')[0].split('\t'))
    except Exception as error:
        logger.debug(f'The polled nodes could not be listed: {error}')
        return None
    return frozenset(names) or None


def snapshot(feature: IValue, protected: bool = False) -> dict[str, object]:
    '''Read *feature*: its access, kind, limits and value.

    *protected* says that the node can be written after acquisition has
    been stopped, so that it counts as ``writable`` although its access
    mode is read-only while the camera runs.

    Returns
    -------
    dict
        ``access`` (:class:`EAccessMode`), ``writable`` (``True`` if the
        node can be written now, or after stopping acquisition) and
        ``kind`` (``'int'``, ``'float'``, ``'enum'``, ``'register'`` or
        ``'other'``) always; ``min``, ``max`` and ``inc`` for numbers
        (``inc`` is ``None`` when the node has no increment); ``entries``
        (symbolic names) for an enumeration; ``length`` and ``address`` for
        a register; and ``value`` when the node is readable.
    '''
    mode = feature.node.get_access_mode()
    kind = nodeKind(feature)
    state = {'access': mode,
             'kind': kind if kind in STATE_KINDS else 'other',
             'writable': mode == EAccessMode.RW or protected}
    state.update(limits(feature, kind))
    if kind == 'register':
        state.update(length=feature.length, address=feature.address)
    if kind in PTYPES and mode in (EAccessMode.RO, EAccessMode.RW):
        state['value'] = read(feature, kind)
    return state
