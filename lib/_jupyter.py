'''Jupyter widget for interactive camera property control.'''
import ipywidgets as widgets
from IPython.display import display as _display

__all__ = ['CameraControls']


class CameraControls:
    '''Interactive property panel for a camera, built from :mod:`ipywidgets`.

    Reads the camera's registered properties and creates an appropriate
    input widget for each one.  Read-only properties are shown but
    disabled.  Clicking **Refresh** re-reads all values from the camera
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

        if value is None:
            try:
                value = ptype()
            except Exception:
                value = 0

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

        elif ptype is int and minimum is not None and maximum is not None:
            s = int(step) if step is not None else max(1, round((maximum - minimum) / 100))
            w = widgets.IntSlider(
                value=int(value), min=int(minimum), max=int(maximum),
                step=s, disabled=disabled, continuous_update=False,
                style={'description_width': '0px'}, layout=layout)

        elif ptype is int:
            w = widgets.IntText(
                value=int(value), disabled=disabled, layout=layout)

        elif minimum is not None and maximum is not None:
            s = float(step) if step is not None else (maximum - minimum) / 100.
            w = widgets.FloatSlider(
                value=float(value), min=float(minimum), max=float(maximum),
                step=s, disabled=disabled, continuous_update=False,
                style={'description_width': '0px'}, layout=layout)

        else:
            w = widgets.FloatText(
                value=float(value), disabled=disabled, layout=layout)

        if not disabled:
            def _on_change(change, _setter=setter, _ptype=ptype):
                if not self._updating:
                    try:
                        _setter(_ptype(change['new']))
                    except Exception:
                        pass
            w.observe(_on_change, names='value')

        return w

    def _build(self) -> widgets.VBox:
        '''Build and return the full widget panel.'''
        label_layout  = widgets.Layout(width='140px', min_width='140px')
        widget_layout = widgets.Layout(flex='1 1 auto', min_width='150px')

        rows = []
        for name, spec in self._camera._properties.items():
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
                except Exception:
                    pass
        finally:
            self._updating = False

    # ------------------------------------------------------------------
    # Jupyter display protocol
    # ------------------------------------------------------------------

    def _repr_mimebundle_(self, **kwargs):
        return self._box._repr_mimebundle_(**kwargs)

    def _ipython_display_(self, **kwargs) -> None:
        _display(self._box, **kwargs)
