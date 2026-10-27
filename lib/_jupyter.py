'''Jupyter front end: camera property controls, live view and chooser.

Everything in this module needs ``ipywidgets``.  The rest of the package
never imports it unless a notebook feature is used, so ``Camera()`` works
without ``ipywidgets`` installed (see :mod:`QVideo.lib._camera`).
'''
import asyncio
import logging
import math
from collections.abc import Callable
from typing import TYPE_CHECKING
import cv2
import ipywidgets as widgets
from IPython.display import display as _display

if TYPE_CHECKING:
    from QVideo.lib.videotypes import Image


logger = logging.getLogger(__name__)

__all__ = ['CameraControls', 'LiveView', 'choose', 'live_view']


def _finite(v) -> bool:
    '''Return True if v is a finite real number.'''
    try:
        return math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


class LiveView:
    '''Handle for a running live video feed.

    Returned by :func:`live_view`.  Call :meth:`stop` to end the update
    loop.
    '''

    def __init__(self, task) -> None:
        self._task = task

    def stop(self) -> None:
        '''Cancel the background update loop.'''
        self._task.cancel()


def live_view(read: Callable[[], 'Image'], fps: float = 30.0) -> LiveView:
    '''Stream the frames that *read* returns into an image widget.

    Encodes each frame as JPEG and updates an :mod:`ipywidgets` ``Image``
    from an ``asyncio`` background loop.  No matplotlib backend switching
    is required.  The feed ends, with a warning, when *read* raises.

    Parameters
    ----------
    read : callable
        Returns one frame as an array each time it is called.
    fps : float
        Target display update rate in frames per second.

    Returns
    -------
    LiveView
        Handle for the running feed.
    '''
    frame = read()

    def _encode(f):
        if f.ndim == 3 and f.shape[2] == 3:
            f = cv2.cvtColor(f, cv2.COLOR_RGB2BGR)
        _, buf = cv2.imencode('.jpg', f)
        return bytes(buf)

    widget = widgets.Image(
        value=_encode(frame),
        format='jpeg',
        width=frame.shape[1],
        height=frame.shape[0],
    )
    _display(widget)

    async def _loop():
        interval = 1.0 / fps
        while True:
            try:
                widget.value = _encode(read())
            except Exception as ex:
                logger.warning(f'live view stopped: {ex}')
                break
            await asyncio.sleep(interval)

    return LiveView(asyncio.ensure_future(_loop()))


async def choose(options: list[tuple[str, object]]) -> object:
    '''Show a drop-down of *options* and return the value that is chosen.

    Parameters
    ----------
    options : list of (str, object)
        A label to show and the value to return for each camera.
    '''
    loop = asyncio.get_running_loop()
    future: asyncio.Future = loop.create_future()

    dropdown = widgets.Dropdown(
        options=options,
        description='Camera:',
        layout=widgets.Layout(width='auto'),
    )
    button = widgets.Button(description='Open', button_style='primary')

    def _on_click(_):
        if not future.done():
            dropdown.disabled = True
            button.disabled = True
            button.button_style = ''
            loop.call_soon_threadsafe(future.set_result, dropdown.value)

    button.on_click(_on_click)
    _display(widgets.HBox([dropdown, button]))
    return await future


class CameraControls:
    '''Interactive property panel for a camera, built from :mod:`ipywidgets`.

    Reads the camera's registered properties and creates an appropriate
    input widget for each one.  Read-only properties are shown but
    disabled.  Properties registered with ``hidden=True`` are omitted
    entirely.  Clicking **Refresh** re-reads all values from the camera
    and updates the display.

    Parameters
    ----------
    camera : QCamera
        An open camera instance.

    Examples
    --------
    In a Jupyter cell::

        camera = await Camera()
        camera.controls()
    '''

    def __init__(self, camera) -> None:
        self._camera = camera
        self._widgets: dict[str, widgets.Widget] = {}
        self._updating = False
        self._box = self._build()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_widget(self, name: str, spec: dict) -> widgets.Widget:
        '''Create an appropriate widget for a single registered property.

        Parameters
        ----------
        name : str
            Property name (used to key ``self._widgets``).
        spec : dict
            Property spec dict from ``camera._properties``.

        Returns
        -------
        widgets.Widget
            A configured, observable widget bound to the property.
        '''
        ptype    = spec.get('ptype', float)
        value    = spec['getter']()
        setter   = spec['setter']
        disabled = setter is None
        minimum  = spec.get('minimum')
        maximum  = spec.get('maximum')
        step     = spec.get('step')
        limits   = spec.get('limits')

        if value is None or (isinstance(value, float) and not _finite(value)):
            try:
                value = ptype()
            except (TypeError, ValueError):
                value = 0

        has_range = (_finite(minimum) and _finite(maximum))

        layout = widgets.Layout(flex='1 1 auto')

        if ptype is bool:
            w = widgets.Checkbox(
                value=bool(value), disabled=disabled,
                indent=False, layout=layout)

        elif ptype is str and limits:
            w = widgets.Dropdown(
                options=limits, value=str(value),
                disabled=disabled, layout=layout)

        elif ptype is str:
            w = widgets.Text(
                value=str(value), disabled=disabled, layout=layout)

        elif ptype is int and has_range:
            s = (int(step) if step is not None
                 else max(1, round((maximum - minimum) / 100)))
            w = widgets.IntSlider(
                value=int(value), min=int(minimum), max=int(maximum),
                step=s, disabled=disabled, continuous_update=False,
                style={'description_width': '0px'}, layout=layout)

        elif ptype is int:
            w = widgets.IntText(
                value=int(value), disabled=disabled, layout=layout)

        elif has_range:
            s = float(step) if step is not None else (maximum - minimum) / 100.
            w = widgets.FloatSlider(
                value=float(value), min=float(minimum), max=float(maximum),
                step=s, disabled=disabled, continuous_update=False,
                style={'description_width': '0px'}, layout=layout)

        else:
            w = widgets.FloatText(
                value=float(value), disabled=disabled, layout=layout)

        if not disabled:
            def _on_change(change, _setter=setter, _ptype=ptype, _name=name):
                if not self._updating:
                    try:
                        _setter(_ptype(change['new']))
                    except Exception as ex:
                        logger.warning(f'cannot set {_name}: {ex}')
            w.observe(_on_change, names='value')

        return w

    def _build(self) -> widgets.VBox:
        '''Build and return the full widget panel.'''
        label_layout  = widgets.Layout(width='140px', min_width='140px')
        widget_layout = widgets.Layout(flex='1 1 auto', min_width='150px')

        rows = []
        for name, spec in self._camera._properties.items():
            if spec.get('hidden'):
                continue
            w = self._make_widget(name, spec)
            w.layout = widget_layout
            self._widgets[name] = w
            label = widgets.Label(
                value=name, layout=label_layout)
            rows.append(widgets.HBox(
                [label, w],
                layout=widgets.Layout(align_items='center', margin='2px 0')))

        refresh_btn = widgets.Button(
            description='Refresh', icon='refresh',
            layout=widgets.Layout(width='110px'))
        refresh_btn.on_click(lambda _: self.refresh())

        title = widgets.HTML(
            value=f'<b>{self._camera.name}</b>',
            layout=widgets.Layout(flex='1 1 auto'))
        header = widgets.HBox(
            [title, refresh_btn],
            layout=widgets.Layout(
                align_items='center', margin='0 0 6px 0'))

        return widgets.VBox(
            [header] + rows,
            layout=widgets.Layout(padding='8px', width='100%'))

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        '''Re-read all property values from the camera and update the widgets.

        Safe to call at any time.  Widget observers are suspended during
        the update so that re-reading a value does not trigger a redundant
        setter call.
        '''
        self._updating = True
        try:
            for name, w in self._widgets.items():
                value = self._camera._properties[name]['getter']()
                if value is None:
                    continue
                try:
                    w.value = type(w.value)(value)
                except Exception as ex:
                    logger.debug(f'cannot show {name}: {ex}')
        finally:
            self._updating = False

    # ------------------------------------------------------------------
    # Jupyter display protocol
    # ------------------------------------------------------------------

    def _repr_mimebundle_(self, **kwargs):
        return self._box._repr_mimebundle_(**kwargs)

    def _ipython_display_(self, **kwargs) -> None:
        _display(self._box, **kwargs)
