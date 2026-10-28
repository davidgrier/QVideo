'''Filter factory — finds filters by name, for notebooks and scripts.

Provides :func:`Filter`, which lists the filters that QVideo provides and
builds them from their display names, so that a notebook needs no imports::

    camera.filters = Filter('Smoothing', 'Canny')
'''
import difflib
from QVideo.lib._camera import _ensure_qapp
from QVideo.lib.QFilterRackWidget import QFilterRackWidget
from QVideo.lib.QVideoFilter import VideoFilter

__all__ = ['Filter']


def _key(name: str) -> str:
    '''Return *name* without spaces or case, for forgiving comparisons.'''
    return ''.join(name.split()).lower()


def Filter(*names: str | list[str] | tuple[str, ...]
           ) -> list[str] | list[VideoFilter]:
    '''List the available filters, or build filters by name.

    Parameters
    ----------
    *names : str or list of str
        Display names of the filters, as separate arguments or in one
        list.  Case and spaces do not matter: ``'darkframe'`` finds
        ``'Dark Frame'``.

    Returns
    -------
    list[str] or list[VideoFilter]
        With no arguments, the sorted display names of all filters.
        Otherwise a new filter with default settings for each name, in
        order, ready to assign to ``camera.filters``.

    Raises
    ------
    ValueError
        If a name matches no filter.  The message suggests close matches.

    Examples
    --------
    ::

        Filter()                                   # what is there?
        camera.filters = Filter('Smoothing', 'Canny')
        camera.filters[1].threshold1 = 50          # change a setting

    Notes
    -----
    Filters that need a calibration, such as ``'Dark Frame'`` and
    ``'Flat Field'``, pass frames through until they have one; call
    ``capture()`` on the filter that you get to take it from the next
    frame.
    '''
    registry = QFilterRackWidget._registry()
    if not names:
        return sorted(registry)
    if len(names) == 1 and isinstance(names[0], (list, tuple)):
        names = tuple(names[0])
    keys = {_key(name): name for name in registry}
    _ensure_qapp()
    filters = []
    for name in names:
        found = keys.get(_key(name))
        if found is None:
            close = difflib.get_close_matches(_key(name), keys, n=3)
            hint = (' Did you mean ' +
                    ' or '.join(repr(keys[k]) for k in close) + '?'
                    if close else ' Filter() lists the names.')
            raise ValueError(f'{name!r} is not a known filter.' + hint)
        filters.append(registry[found]().filter)
    return filters
