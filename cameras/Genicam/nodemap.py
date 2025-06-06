from genicam.genapi import (IValue, ICategory, ICommand, IEnumeration,
                            IBoolean, IInteger, IFloat, IString)
from genicam.genapi import EAccessMode
import logging


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


def _todict(feature: IValue) -> dict:
    '''Return a dictionary describing the node map starting from a feature'''
    this = dict(name=feature.node.name,
                title=feature.node.display_name)
    if isinstance(feature, ICommand):
        this['type'] = 'action'
        return this
    if isinstance(feature, ICategory):
        this['type'] = 'group'
        children = [_todict(f) for f in feature.features]
        this['children'] = children
        return this
    mode = feature.node.get_access_mode()
    if mode not in (EAccessMode.RW, EAccessMode.RO):
        this['visible'] = False
        return this
    this['enabled'] = (mode == EAccessMode.RW)
    if isinstance(feature, IEnumeration):
        this['type'] = 'list'
        this['value'] = feature.to_string()
        this['limits'] = [v.symbolic for v in feature.entries]
    elif isinstance(feature, IBoolean):
        this['type'] = 'bool'
        this['value'] = feature.value
    elif isinstance(feature, IInteger):
        this['type'] = 'int'
        this['value'] = feature.value
        this['min'] = feature.min
        this['max'] = feature.max
        this['step'] = feature.inc
    elif isinstance(feature, IFloat):
        this['type'] = 'float'
        this['value'] = feature.value
        this['min'] = feature.min
        this['max'] = feature.max
        this['units'] = feature.unit
        if feature.has_inc():
            this['step'] = feature.inc
    elif isinstance(feature, IString):
        this['type'] = 'str'
        this['value'] = feature.value
    else:
        logger.debug(
            f'Unsupported node type: {feature.node.name}: {type(feature)}')
    return this


def _enabled(feature: IValue) -> bool:
    if isinstance(feature, (ICategory, IControl)):
        return True
    return (feature.node.get_access_mode() == EAccessMode.RW)


def _properties(feature: IValue) -> list[str]:
    '''Return a list of accessible properties'''
    this = []
    if isinstance(feature, ICategory):
        for f in feature.features:
            this.extend(_properties(f))
    elif isinstance(feature, (IEnumeration, IBoolean, IInteger, IFloat)):
        if feature.node.get_access_mode() == EAccessMode.RW:
            this = [feature.node.name]
    return this


def _methods(feature: IValue) -> list[str]:
    '''Return a list of executable methods'''
    this = []
    if isinstance(feature, ICategory):
        for f in feature.features:
            this.extend(_methods(f))
    elif isinstance(feature, ICommand):
        this = [feature.node.name]
    return this


def _set(feature: IValue, value: bool | int | float | str):
    '''Set the value of a feature'''
    mode = feature.node.get_access_mode()
    if mode not in (EAccessMode.RW, EAccessMode.WO):
        return
    if isinstance(feature, IEnumeration):
        feature.node.from_string(value)
    else:
        feature.value = value


def _get(feature: IValue) -> bool | int | float | str | None:
    '''Return the value of a feature'''
    mode = feature.node.get_access_mode()
    if mode not in (EAccessMode.RW, EAccessMode.RO):
        return None
    if isinstance(feature, IEnumeration):
        return feature.to_string()
    else:
        return feature.value


def _execute(feature: IValue) -> None:
    '''Execute command node'''
    if isinstance(feature, ICommand):
        feature.execute()
