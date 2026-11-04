'''The application that a camera needs before it is made.'''
__all__ = ['ensure_qapp']

#: Keeps the application that :func:`ensure_qapp` makes alive.
_keep: list = []


def ensure_qapp() -> None:
    '''Create a QApplication if none exists (required before any QCamera).

    The application is kept in a module variable: if nothing refers to it,
    Python deletes it again as soon as this function returns.
    '''
    from qtpy.QtWidgets import QApplication
    if QApplication.instance() is None:
        _keep.append(QApplication([]))
