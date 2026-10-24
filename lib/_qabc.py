'''Metaclass for abstract Qt classes.'''
from abc import ABCMeta
from qtpy import QtCore

__all__ = ['QABCMeta']


class QABCMeta(ABCMeta, type(QtCore.QObject)):

    '''Metaclass that lets a ``QObject`` subclass use ``@abstractmethod``.

    Python requires one metaclass that derives from both
    :class:`abc.ABCMeta` and the metaclass of
    :class:`~qtpy.QtCore.QObject`, which is binding specific.  Neither Qt
    binding provides one.

    ``ABCMeta`` must come first.  PyQt accepts either order.  Under
    PySide6, ``ABCMeta.__new__`` must run before Shiboken's metaclass: with
    the opposite order the abstract-class bookkeeping is skipped and
    ``isinstance()`` raises ``AttributeError``.  That order is accepted
    from PySide6 6.7 (see PYSIDE-1767 in the Qt bug tracker); earlier
    releases raise ``TypeError`` when the class is created.

    Shiboken does not check abstract methods when an object is created, so
    under PySide6 an incomplete subclass can be instantiated; the missing
    method fails when it is called.
    '''
