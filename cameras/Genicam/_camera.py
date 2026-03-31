from QVideo.lib import QCamera, QVideoSource
import numpy as np
import os
import logging
from pathlib import Path

try:
    from harvesters.core import Harvester
    from genicam.genapi import (IValue, EAccessMode, EVisibility,
                                ICategory, ICommand, IEnumeration,
                                IBoolean, IInteger, IFloat, IString)
    from genicam.gentl import TimeoutException
    IProperty = (IEnumeration, IBoolean, IInteger, IFloat, IString)
except (ImportError, ModuleNotFoundError) as exc:
    raise ImportError(
        f"QGenicamCamera could not import 'genicam': {exc}\n"
        '\tInstall it with: pip install genicam harvesters\n'
        '\tIf the error persists, try downgrading to numpy 1.x:\n'
        '\t  pip install "numpy<2"'
    ) from exc


logger = logging.getLogger(__name__)


__all__ = ['QGenicamCamera', 'QGenicamSource']


class QGenicamCamera(QCamera):

    '''Abstract base for GenICam-compliant cameras accessed via Harvesters.

    `GenICam <https://www.emva.org/standards-technology/genicam/>`_ is a
    standardized machine-vision interface maintained by the European Machine
    Vision Association.  Communication with the physical device is handled by
    a GenTL producer — a ``.cti`` binary supplied by the camera manufacturer.

    Subclasses **must** set the :attr:`producer` class attribute to the path
    of the appropriate ``.cti`` file before instantiating.  Attempting to
    instantiate :class:`QGenicamCamera` directly raises :exc:`TypeError`.

    Requires the ``genicam`` and ``harvesters`` packages
    (``pip install genicam harvesters``).

    Attributes
    ----------
    producer : str or None
        Path to the GenTL producer ``.cti`` file.  Must be overridden by
        concrete subclasses.

    Parameters
    ----------
    cameraID : int
        Index of the camera to open.  Default: ``0``.
    *args :
        Forwarded to :class:`~QVideo.lib.QCamera`.
    **kwargs :
        Forwarded to :class:`~QVideo.lib.QCamera`.
    '''

    producer: str | None = None

    @staticmethod
    def _findProducer(*filenames: str) -> 'str | None':
        '''Search GENICAM_GENTL64_PATH for a matching GenTL producer.

        Parameters
        ----------
        *filenames : str
            Producer ``.cti`` filenames to search for, in priority order.

        Returns
        -------
        str or None
            Absolute path to the first ``.cti`` file found, or ``None`` if
            none of the requested producers exist on the path.
        '''
        search_path = os.environ.get('GENICAM_GENTL64_PATH', '')
        for directory in search_path.split(os.pathsep):
            for name in filenames:
                candidate = Path(directory) / name
                if candidate.exists():
                    return str(candidate)
        return None

    @staticmethod
    def _set_feature(feature: IValue,
                     value: QCamera.PropertyValue) -> None:
        '''Set the value of a feature node.'''
        logger.debug(f'Setting {feature.node.name}: {value}')
        if isinstance(feature, IEnumeration):
            if value in [v.symbolic for v in feature.entries]:
                feature.from_string(value)
            else:
                logger.warning(f'{value} is not in {feature.node.name}')
        elif isinstance(feature, IBoolean):
            feature.value = bool(value)
        elif isinstance(feature, IInteger):
            value = np.clip(value, feature.min, feature.max)
            value = (value - feature.min) // feature.inc
            feature.value = int(value * feature.inc + feature.min)
        elif isinstance(feature, IFloat):
            feature.value = float(np.clip(value, feature.min, feature.max))
        elif isinstance(feature, IString):
            feature.value = str(value)

    @staticmethod
    def _make_getter(feature: IValue):
        '''Return a zero-argument callable that reads the feature value.

        The returned callable checks the current access mode before reading,
        returning ``None`` for features that are not readable at call time
        (e.g. enumeration nodes whose access mode changes after acquisition
        starts).
        '''
        if isinstance(feature, IEnumeration):
            def getter():
                if feature.node.get_access_mode() in (EAccessMode.RO, EAccessMode.RW):
                    return feature.to_string()
                return None
            return getter

        def getter():
            if feature.node.get_access_mode() in (EAccessMode.RO, EAccessMode.RW):
                return feature.value
            return None
        return getter

    @staticmethod
    def _feature_ptype(feature: IValue) -> type:
        '''Return the Python type for a feature.'''
        if isinstance(feature, IBoolean):
            return bool
        if isinstance(feature, IInteger):
            return int
        if isinstance(feature, IFloat):
            return float
        return str  # IEnumeration, IString

    @staticmethod
    def _feature_meta(feature: IValue) -> dict:
        '''Return extra metadata kwargs for registerProperty.'''
        if isinstance(feature, IEnumeration):
            return {'limits': [v.symbolic for v in feature.entries]}
        if isinstance(feature, IInteger):
            return {'minimum': feature.min, 'maximum': feature.max,
                    'step': feature.inc}
        if isinstance(feature, IFloat):
            meta = {'minimum': feature.min, 'maximum': feature.max}
            if feature.has_inc():
                meta['step'] = feature.inc
            return meta
        return {}

    @staticmethod
    def _scan_modes(feature: IValue) -> dict[str, object]:
        '''Return a dict mapping property node names to their access modes.'''
        modes = {}
        if isinstance(feature, ICategory):
            for f in feature.features:
                modes.update(QGenicamCamera._scan_modes(f))
        elif isinstance(feature, IProperty):
            modes[feature.node.name] = feature.node.get_access_mode()
        return modes

    def _make_setter(self, feature: IValue, name: str):
        '''Return a setter that checks current access mode before writing.

        If the feature is not currently writable (and is not a protected
        feature that can be written after stopping acquisition), the write
        is skipped and a warning is logged.  Protected features stop and
        restart acquisition around the write as before.
        '''
        def setter(value):
            mode = feature.node.get_access_mode()
            if mode != EAccessMode.RW and name not in self.protected:
                logger.warning(
                    f'{name} is not currently writable (mode={mode})')
                return
            restart = name in self.protected and self.device.is_acquiring()
            if restart:
                self.device.stop()
            QGenicamCamera._set_feature(feature, value)
            if restart:
                self.device.start()
        return setter

    def _register_features(self, feature: IValue) -> None:
        '''Recurse the node tree to register properties and methods.'''
        if isinstance(feature, ICategory):
            for f in feature.features:
                self._register_features(f)
        elif isinstance(feature, ICommand):
            self.registerMethod(feature.node.name, feature.execute)
        elif isinstance(feature, IProperty):
            mode = feature.node.get_access_mode()
            if mode not in (EAccessMode.RO, EAccessMode.RW):
                return
            name = feature.node.name
            getter = self._make_getter(feature)
            setter = self._make_setter(feature, name)
            self.registerProperty(name,
                                  getter=getter,
                                  setter=setter,
                                  ptype=self._feature_ptype(feature),
                                  **self._feature_meta(feature))

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        if cls.producer is None:
            raise TypeError(
                f"{cls.__name__} must define a 'producer' class attribute "
                'naming a GenTL producer .cti file.')

    def __init__(self, *args, cameraID: int = 0, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.cameraID = cameraID
        self.nodeMap = None
        self.open()

    def _initialize(self) -> bool:
        '''Open the GenICam device and register available properties.

        Returns
        -------
        bool
            ``True`` if a valid camera device was opened successfully.
        '''
        self.harvester = Harvester()
        self.device = None
        try:
            self.harvester.add_file(self.producer)
            self.harvester.update()
        except Exception as ex:
            logger.warning(
                f'Failed to load producer {self.producer!r}: {ex}')
            self._cleanup()
            return False
        try:
            self.device = self.harvester.create(self.cameraID)
        except Exception as ex:
            logger.warning(
                f'No camera found at index {self.cameraID}: {ex}')
            self._cleanup()
            return False
        if self.device.remote_device is None:
            logger.warning('Camera remote device is not available')
            self._cleanup()
            return False
        self.nodeMap = self.device.remote_device.node_map
        root = self.node()
        ma = self._scan_modes(root)
        self.device.start()
        mb = self._scan_modes(root)
        self.protected = {k for k, v in ma.items()
                          if k in mb and mb[k] != v}
        self._register_features(root)
        for genicam_name, alias in (('Width', 'width'), ('Height', 'height')):
            if genicam_name in self._properties:
                orig_setter = self._properties[genicam_name]['setter']
                if orig_setter is not None:
                    def _shape_setter(v, s=orig_setter):
                        s(v)
                        self.shapeChanged.emit(self.shape)
                    self._properties[genicam_name]['setter'] = _shape_setter
                self._properties[alias] = self._properties[genicam_name]
        if not self.device.is_valid():
            logger.warning(
                'Camera device reported invalid after initialization')
            self._cleanup()
            return False
        return True

    def _cleanup(self) -> None:
        '''Release partially initialized resources after a failed _initialize.

        Safe to call regardless of how far initialization progressed.
        Each step is guarded so that a failure here does not mask the
        original exception.
        '''
        if self.device is not None:
            try:
                self.device.stop()
            except Exception:
                pass
            try:
                self.device.destroy()
            except Exception:
                pass
            self.device = None
        try:
            self.harvester.reset()
        except Exception:
            pass
        self.nodeMap = None

    def _deinitialize(self) -> None:
        '''Stop acquisition and release the GenICam device.'''
        self._cleanup()

    def read(self) -> QCamera.CameraData:
        '''Read one frame from the camera.

        Returns
        -------
        tuple[bool, ndarray or None]
            ``(True, frame)`` on success, ``(False, None)`` on timeout.
        '''
        frame = None
        try:
            with self.device.fetch(timeout=1) as buffer:
                components = buffer.payload.components
                if not components:
                    logger.warning('camera returned empty payload')
                    return False, None
                image = components[0]
                height = image.height
                width = image.width
                channels = int(image.num_components_per_pixel)
                frame = image.data.copy()
            frame = frame.reshape(height, width, channels).squeeze()
        except TimeoutException:
            logger.warning('camera acquisition timed out')
        except Exception as e:
            logger.warning(f'camera read failed: {e}')
        return frame is not None, frame

    def has_node(self, name: str) -> bool:
        '''Return ``True`` if the named node exists in the node map.

        Unlike :meth:`node`, this never logs a warning for missing names.
        Use it to guard calls to :meth:`node` or :meth:`is_readwrite` in
        reactive code paths (e.g. UI update loops) where absent names are
        expected and not an error.

        Parameters
        ----------
        name : str
            GenICam node name to look up.

        Returns
        -------
        bool
            ``True`` if the node map is available and contains *name*.
        '''
        return self.nodeMap is not None and self.nodeMap.has_node(name)

    def node(self, name: str = 'Root') -> 'IValue | None':
        '''Return the GenICam node with the given name.

        Parameters
        ----------
        name : str
            Node name to look up.  Default: ``'Root'``.

        Returns
        -------
        IValue or None
            The requested node, or ``None`` if it does not exist.
        '''
        if self.nodeMap is None:
            return None
        if self.nodeMap.has_node(name):
            return self.nodeMap.get_node(name)
        logger.warning(f'node {name} is unknown')
        return None

    _SHAPE_ALIASES = frozenset(('width', 'height'))

    @property
    def settings(self) -> QCamera.Settings:
        '''All registered property values, excluding lowercase shape aliases.

        GenICam cameras register ``width``/``height`` as lowercase aliases for
        ``Width``/``Height`` so that :attr:`~QVideo.lib.QCamera.QCamera.shape`
        and attribute access (``camera.width``) work the same as on other
        backends.  Those aliases are excluded here so that
        :class:`~QVideo.cameras.Genicam._tree.QGenicamTree` does not try to
        sync them to tree parameters (which use the canonical GenICam names).
        '''
        return {name: spec['getter']()
                for name, spec in self._properties.items()
                if name not in self._SHAPE_ALIASES}

    @settings.setter
    def settings(self, settings: QCamera.Settings) -> None:
        for key, value in settings.items():
            self.set(key, value)

    def is_readwrite(self, feature: str) -> bool:
        '''Return ``True`` if the named feature is currently writable.

        Parameters
        ----------
        feature : str
            GenICam node name.

        Returns
        -------
        bool
            ``True`` if the feature is writable, or protected (writable
            after stopping acquisition).
        '''
        node = self.node(feature)
        if node is None:
            return False
        mode = node.node.get_access_mode()
        return (mode == EAccessMode.RW) or (feature in self.protected)


class QGenicamSource(QVideoSource):

    '''Threaded video source backed by :class:`QGenicamCamera`.

    Parameters
    ----------
    camera : QGenicamCamera
        Camera instance to wrap.
    '''

    def __init__(self, camera: QGenicamCamera) -> None:
        super().__init__(camera)


if __name__ == '__main__':  # pragma: no cover
    QGenicamCamera.example()
