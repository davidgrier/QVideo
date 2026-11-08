'''What an application remembers from one session to the next.

Only a named application remembers anything.  Qt names an application that
nobody named after the interpreter (``Python``), and such a program would
share one set of settings with every other script, so it gets none: the
functions here remember nothing and recall the default.  An application
names itself with ``QCoreApplication.setApplicationName`` (``launch()``
does so from its title).  The settings are the platform's own: a property
list on macOS, a configuration file on Linux, the registry on Windows.
'''
from pathlib import Path
import logging
import sys

from qtpy import QtCore


logger = logging.getLogger(__name__)

__all__ = ['isNamed', 'recall', 'remember']

#: The organization of an application that has not set one.
ORGANIZATION = 'QVideo'


def isNamed() -> bool:
    '''Return whether the application has a name of its own.'''
    name = QtCore.QCoreApplication.applicationName()
    interpreter = Path(sys.executable).stem.casefold()
    return bool(name) and name.casefold() != interpreter


def _open() -> QtCore.QSettings | None:
    '''Return the settings of the application, or ``None`` without a name.'''
    if not isNamed():
        return None
    organization = (QtCore.QCoreApplication.organizationName()
                    or ORGANIZATION)
    return QtCore.QSettings(organization,
                            QtCore.QCoreApplication.applicationName())


def recall(key: str, default: str = '') -> str:
    '''Return the text that was remembered under *key*, or *default*.'''
    settings = _open()
    if settings is None:
        return default
    value = settings.value(key, default)
    return value if isinstance(value, str) else default


def remember(key: str, value: str) -> None:
    '''Remember *value* under *key* for the next session.

    A settings file that cannot be written is logged and otherwise ignored.
    '''
    settings = _open()
    if settings is None:
        return
    settings.setValue(key, value)
    settings.sync()
    if settings.status() != QtCore.QSettings.Status.NoError:
        logger.warning(f'cannot remember {key!r}: {settings.fileName()}')
