from collections.abc import Callable
from typing import TYPE_CHECKING
from QVideo.lib import QCamera, QVideoSource
import numpy as np
import os
import logging
from pathlib import Path

if TYPE_CHECKING:
    from harvesters.core import ImageAcquirer
    from genicam.genapi import NodeMap

try:
    from harvesters.core import Harvester
    from genicam.genapi import (IValue, EAccessMode, ICategory, ICommand,
                                IEnumeration, IBoolean, IInteger, IFloat,
                                IString)
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

    producer: str | Path | None = None
    _producer_filenames: tuple[str, ...] = ()
    _ALIASES = frozenset(('width', 'height', 'fps'))

    def __init__(self, *args, cameraID: int = 0, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._cameraID = cameraID
        self._harvester: Harvester | None = None
        self._device: 'ImageAcquirer | None' = None
        self._nodeMap: 'NodeMap | None' = None
        self._protected: set[str] = set()
        self.open()

    def _initialize(self) -> bool:
        '''Open the GenICam device and register available properties.

        Returns
        -------
        bool
            ``True`` if a valid camera device was opened successfully.
        '''
        producer = (self.producer
                    or self._findProducer(*self._producer_filenames))
        if producer is None:
            logger.warning(
                f'{type(self).__name__}: no GenTL producer available '
                f'(set GENICAM_GENTL64_PATH before opening the camera)')
            return False
        self._harvester = Harvester()
        self._device = None
        try:
            self._harvester.add_file(producer)
            self._harvester.update()
        except Exception as ex:
            logger.warning(
                f'Failed to load producer {producer!r}: {ex}')
            self._cleanup()
            return False
        try:
            self._device = self._harvester.create(self._cameraID)
        except Exception as ex:
            logger.warning(
                f'No camera found at index {self._cameraID}: {ex}')
            self._cleanup()
            return False
        self._nodeMap = self._device.remote_device.node_map
        if not self._nodeMap.has_node('Root'):
            logger.warning('harvesters node map unconnected; '
                           'loading manually from device port')
            self._nodeMap = self._load_node_map(self._device)
            if self._nodeMap is None:
                self._cleanup()
                return False
        root = self.node()
        ma = self._scan_modes(root)
        self._device.start()
        mb = self._scan_modes(root)
        self._protected = {k for k, v in ma.items()
                          if k in mb and mb[k] != v}
        self._register_features(root)
        try:
            self._modelName = str(self._nodeMap.DeviceModelName.value)
        except Exception:
            pass
        for src, dst in (('Width', 'width'), ('Height', 'height'),
                         ('AcquisitionFrameRate', 'fps'),
                         ('AcquisitionFrameRateAbs', 'fps')):
            if src in self._properties and dst not in self._properties:
                self._properties[dst] = self._properties[src]
        return True

    def _cleanup(self) -> None:
        '''Release partially initialized resources after a failed _initialize.

        Safe to call regardless of how far initialization progressed.
        Each step is guarded so that a failure here does not mask the
        original exception.
        '''
        if self._device is not None:
            try:
                self._device.stop()
            except Exception:
                pass
            try:
                self._device.destroy()
            except Exception:
                pass
            self._device = None
        try:
            self._harvester.reset()
        except Exception:
            pass
        self._nodeMap = None

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
            with self._device.fetch(timeout=1) as buffer:
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

    @property
    def settings(self) -> QCamera.Settings:
        '''All registered property values, excluding standard-name aliases.

        GenICam cameras register lowercase aliases (``width``, ``height``,
        ``fps``) that map to canonical SFNC node names (``Width``, ``Height``,
        ``AcquisitionFrameRate``).  Those aliases are excluded here so that
        :class:`~QVideo.cameras.Genicam._tree.QGenicamTree` does not try to
        sync them to tree parameters — the canonical names are already
        present and do the right thing.  Attribute access
        (``camera.fps``) still works
        because :meth:`~QVideo.lib.QCamera.QCamera.__getattr__` reads
        ``_properties`` directly, not ``settings``.
        '''
        return {name: spec['getter']()
                for name, spec in self._properties.items()
                if name not in self._ALIASES}

    @settings.setter
    def settings(self, settings: QCamera.Settings) -> None:
        for key, value in settings.items():
            self.set(key, value)

    def set(self, key: str, value: QCamera.PropertyValue) -> None:
        super().set(key, value)
        if key.lower() in ('width', 'height'):
            self.shapeChanged.emit(self.shape)

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
    def _load_node_map(device: 'ImageAcquirer') -> 'NodeMap | None':
        '''Reload the node map by re-running harvesters' own loading logic.

        Called when harvesters' automatic node map loading fails due to a
        timing race: if the Spinnaker GenTL producer's port URL list is not
        yet populated at ``h.create()`` time, harvesters silently returns an
        unconnected ``NodeMap``.  Calling ``_create_node_map`` again once the
        port has settled produces a connected map, which is then patched back
        onto the device so that ``device.start()`` also uses it.

        .. warning::
            Accesses ``device.remote_device._create_node_map``, a private
            harvesters API.  Validated against harvesters 1.x; may break
            if harvesters internals change.

        Parameters
        ----------
        device : ImageAcquirer
            The device whose remote port will be queried.

        Returns
        -------
        NodeMap or None
            A connected node map, or ``None`` if loading failed.
        '''
        try:
            port = device.remote_device.module.remote_port
            nm = device.remote_device._create_node_map(port=port)
            device.remote_device._node_map = nm
            return nm
        except Exception as exc:
            logger.warning(f'manual node map load failed: {exc}')
            return None

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

    @staticmethod
    def _make_getter(feature: IValue) -> Callable[[], object]:
        '''Return a zero-argument callable that reads the feature value.

        The returned callable checks the current access mode before reading,
        returning ``None`` for features that are not readable at call time
        (e.g. enumeration nodes whose access mode changes after acquisition
        starts).
        '''
        is_enum = isinstance(feature, IEnumeration)

        def getter():
            mode = feature.node.get_access_mode()
            if mode not in (EAccessMode.RO, EAccessMode.RW):
                return None
            return feature.to_string() if is_enum else feature.value
        return getter

    def _make_setter(self,
                     feature: IValue,
                     name: str) -> Callable[[QCamera.PropertyValue], None]:
        '''Return a setter that checks current access mode before writing.

        If the feature is not currently writable (and is not a protected
        feature that can be written after stopping acquisition), the write
        is skipped and a warning is logged.  Protected features stop and
        restart acquisition around the write as before.
        '''
        def setter(value):
            mode = feature.node.get_access_mode()
            if mode != EAccessMode.RW and name not in self._protected:
                logger.warning(
                    f'{name} is not currently writable (mode={mode})')
                return
            restart = name in self._protected and self._device.is_acquiring()
            if restart:
                self._device.stop()
            QGenicamCamera._set_feature(feature, value)
            if restart:
                self._device.start()
        return setter

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
            value = int(np.clip(value, feature.min, feature.max))
            steps = round((value - feature.min) / feature.inc)
            feature.value = int(np.clip(
                steps * feature.inc + feature.min, feature.min, feature.max))
        elif isinstance(feature, IFloat):
            feature.value = float(np.clip(value, feature.min, feature.max))
        elif isinstance(feature, IString):
            feature.value = str(value)

    @staticmethod
    def _feature_spec(feature: IValue) -> tuple[type, dict[str, object]]:
        '''Return the Python type and registerProperty metadata for a feature.

        IEnumeration must be checked before IInteger: in Spinnaker's SDK
        IEnumeration inherits from IInteger, so the order is significant.
        '''
        if isinstance(feature, IEnumeration):
            return str, {'limits': [v.symbolic for v in feature.entries]}
        if isinstance(feature, IBoolean):
            return bool, {}
        if isinstance(feature, IInteger):
            return int, {'minimum': feature.min, 'maximum': feature.max,
                         'step': feature.inc}
        if isinstance(feature, IFloat):
            meta = {'minimum': feature.min, 'maximum': feature.max}
            if feature.has_inc():
                meta['step'] = feature.inc
            return float, meta
        return str, {}

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
            ptype, meta = self._feature_spec(feature)
            self.registerProperty(name,
                                  getter=self._make_getter(feature),
                                  setter=self._make_setter(feature, name),
                                  ptype=ptype,
                                  **meta)

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
        return self._nodeMap is not None and self._nodeMap.has_node(name)

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
        if self._nodeMap is None:
            return None
        if self._nodeMap.has_node(name):
            return self._nodeMap.get_node(name)
        logger.warning(f'node {name} is unknown')
        return None

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
        return (mode == EAccessMode.RW) or (feature in self._protected)


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
