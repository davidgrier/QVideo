'''QR codes, drawn from the ``segno`` package.

The one place that imports ``segno`` (the ``stream`` extra), so that a
program that does not show a code never needs it.
'''
from __future__ import annotations

__all__ = ['matrix', 'terminal']


def _make(text: str):
    try:
        import segno
    except ImportError as error:
        raise ImportError('QR codes need segno: '
                          'pip install "QVideo[stream]"') from error
    return segno.make(text, error='m')


def matrix(text: str) -> list[list[bool]]:
    '''Return the modules of the QR code of *text*, rows of ``True`` for
    dark, without the quiet zone.

    Raises
    ------
    ImportError
        If ``segno`` is not installed.
    '''
    return [[bool(module) for module in row] for row in _make(text).matrix]


def terminal(text: str) -> str:
    '''Return the QR code of *text* as text that a terminal can show.'''
    import io
    out = io.StringIO()
    _make(text).terminal(out=out, compact=True)
    return out.getvalue()
