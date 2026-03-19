'''Unit tests for QGenicamTree.'''
import sys
import unittest
from unittest.mock import MagicMock, patch
from pyqtgraph.Qt import QtWidgets


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


# ---------------------------------------------------------------------------
# Module-level stub setup.
#
# QGenicamTree uses @pyqtProperty(EVisibility) at class-definition time,
# so EVisibility must be a real Python type — not a MagicMock.
#
# Strategy: define a proper EVisibility int subclass, then either update an
# already-loaded 'genicam.genapi' mock (e.g. set by test_qgenicamcamera.py)
# or install fresh stubs.  A QGenicamTree stub set by test_qgenicamcamera.py
# is removed so the real class is loaded with our proper EVisibility.
# ---------------------------------------------------------------------------

class _EVisibility(int):
    '''Stand-in for genicam.genapi.EVisibility (must be a real Python type).'''


_EVisibility.Beginner  = _EVisibility(0)
_EVisibility.Expert    = _EVisibility(1)
_EVisibility.Guru      = _EVisibility(2)
_EVisibility.Invisible = _EVisibility(99)


class _IValue:                pass
class _ICategory(_IValue):    pass
class _ICommand(_IValue):     pass
class _IEnumeration(_IValue): pass
class _IBoolean(_IValue):     pass
class _IInteger(_IValue):     pass
class _IFloat(_IValue):       pass
class _IString(_IValue):      pass


class _EAccessMode:
    RW = 'RW'
    RO = 'RO'
    WO = 'WO'
    NI = 'NI'


class _TimeoutException(Exception):
    pass


def _install_genapi_stubs() -> None:
    '''Install or update the genicam.genapi mock with a real EVisibility.'''
    existing = sys.modules.get('genicam.genapi')
    if existing is not None:
        # Already loaded (e.g. by test_qgenicamcamera.py).  Only update
        # EVisibility — do NOT replace the IValue type stubs.  Replacing
        # them would break isinstance checks in modules that imported the
        # original types before this file ran.
        existing.EVisibility = _EVisibility
    else:
        mock_genapi = MagicMock()
        mock_genapi.EVisibility  = _EVisibility
        mock_genapi.IValue       = _IValue
        mock_genapi.ICategory    = _ICategory
        mock_genapi.ICommand     = _ICommand
        mock_genapi.IEnumeration = _IEnumeration
        mock_genapi.IBoolean     = _IBoolean
        mock_genapi.IInteger     = _IInteger
        mock_genapi.IFloat       = _IFloat
        mock_genapi.IString      = _IString
        mock_genapi.EAccessMode  = _EAccessMode
        mock_genapi.IProperty    = (
            _IEnumeration | _IBoolean | _IInteger | _IFloat | _IString)
        mock_gentl                  = MagicMock()
        mock_gentl.TimeoutException = _TimeoutException
        mock_harvesters_core = MagicMock()
        mock_harvesters      = MagicMock()
        mock_harvesters.core = mock_harvesters_core
        for name, mod in [
            ('harvesters',      mock_harvesters),
            ('harvesters.core', mock_harvesters_core),
            ('genicam',         MagicMock()),
            ('genicam.genapi',  mock_genapi),
            ('genicam.gentl',   mock_gentl),
        ]:
            sys.modules.setdefault(name, mod)


_install_genapi_stubs()

# Remove any MagicMock stub for QGenicamTree so the real class is loaded.
for _key in list(sys.modules):
    if 'QGenicamTree' in _key:
        del sys.modules[_key]

from QVideo.cameras.Genicam.QGenicamCamera import QGenicamCamera  # noqa: E402
from QVideo.cameras.Genicam.QGenicamTree import QGenicamTree      # noqa: E402

_cam_module  = sys.modules['QVideo.cameras.Genicam.QGenicamCamera']
_tree_module = sys.modules['QVideo.cameras.Genicam.QGenicamTree']

# Use the exact class objects that the loaded modules reference.
_ICategory    = _tree_module.ICategory
_ICommand     = _tree_module.ICommand
_IEnumeration = _tree_module.IEnumeration
_IBoolean     = _tree_module.IBoolean
_IInteger     = _tree_module.IInteger
_IFloat       = _tree_module.IFloat
_IString      = _tree_module.IString
_EAccessMode  = _tree_module.EAccessMode
_EVisibility  = _tree_module.EVisibility


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PRODUCER = '/fake/producer.cti'


class _ConcreteCamera(QGenicamCamera):
    '''Minimal concrete subclass with a fixed producer for testing.'''
    producer = PRODUCER


def _make_feature(ftype, name, *, mode=None, visibility=None, **kw):
    '''Return a MagicMock that passes isinstance(f, ftype) checks.

    Setting __class__ makes isinstance work without restricting the mock's
    attribute space (same pattern as test_qgenicamcamera.py).
    '''
    if mode is None:
        mode = _EAccessMode.RW
    if visibility is None:
        visibility = _EVisibility.Beginner
    f = MagicMock()
    f.__class__ = ftype
    f.node = MagicMock()
    f.node.name = name
    f.node.display_name = name
    f.node.visibility = visibility
    f.node.get_access_mode.return_value = mode
    for k, v in kw.items():
        setattr(f, k, v)
    return f


def _int_feature(name='Width', value=640, min=64, max=1920, inc=4,
                 mode=None, visibility=None):
    return _make_feature(_IInteger, name, mode=mode, visibility=visibility,
                         value=value, min=min, max=max, inc=inc)


def _float_feature(name='Gamma', value=1.0, min=0.1, max=4.0, unit='',
                   has_inc=True, inc=0.1, mode=None, visibility=None):
    f = _make_feature(_IFloat, name, mode=mode, visibility=visibility,
                      value=value, min=min, max=max, unit=unit, inc=inc)
    f.has_inc.return_value = has_inc
    return f


def _enum_feature(name='PixelFormat', value='Mono8',
                  entries=('Mono8', 'RGB8'), mode=None, visibility=None):
    f = _make_feature(_IEnumeration, name, mode=mode, visibility=visibility)
    f.to_string.return_value = value
    f.entries = []
    for sym in entries:
        entry = MagicMock()
        entry.symbolic = sym
        f.entries.append(entry)
    return f


def _bool_feature(name='ReverseX', value=False, mode=None, visibility=None):
    return _make_feature(_IBoolean, name, mode=mode, visibility=visibility,
                         value=value)


def _str_feature(name='DeviceUserID', value='cam0', mode=None, visibility=None):
    return _make_feature(_IString, name, mode=mode, visibility=visibility,
                         value=value)


def _cmd_feature(name='AcquisitionStop', visibility=None):
    f = _make_feature(_ICommand, name, visibility=visibility)
    return f


def _cat_feature(name='ImageFormat', features=(), visibility=None):
    f = MagicMock()
    f.__class__ = _ICategory
    f.node = MagicMock()
    f.node.name = name
    f.node.display_name = name
    f.node.visibility = visibility or _EVisibility.Beginner
    f.node.get_access_mode.return_value = _EAccessMode.RW
    f.features = list(features)
    return f


def _make_node_map(features):
    '''Return (node_map_mock, root_category) with smart get_node dispatch.'''
    nm = MagicMock()
    root = _cat_feature('Root', features)
    feat_by_name = {'Root': root}
    feat_by_name.update({f.node.name: f for f in features})
    nm.has_node.side_effect  = lambda n: n in feat_by_name
    nm.get_node.side_effect  = lambda n: feat_by_name.get(n)
    return nm, root


def make_camera(features=()):
    '''Return an open _ConcreteCamera backed by the given features.'''
    nm, _ = _make_node_map(list(features))
    device = MagicMock()
    device.is_valid.return_value     = True
    device.is_acquiring.return_value = False
    device.remote_device.node_map    = nm
    harvester = MagicMock()
    harvester.create.return_value = device
    with patch.object(_cam_module, 'Harvester', return_value=harvester):
        cam = _ConcreteCamera()
    return cam, nm


def make_tree(features=(), visibility=None, controls=None):
    '''Return a QGenicamTree backed by a camera with the given features.'''
    if visibility is None:
        visibility = _EVisibility.Guru
    cam, nm = make_camera(features)
    tree = QGenicamTree(camera=cam, visibility=visibility, controls=controls)
    return tree, cam, nm


# ---------------------------------------------------------------------------
# TestInit
# ---------------------------------------------------------------------------

class TestInit(unittest.TestCase):

    def test_camera_accessible(self):
        tree, cam, _ = make_tree()
        self.assertIs(tree.camera, cam)

    def test_empty_tree_has_no_parameters(self):
        tree, _, _ = make_tree()
        self.assertEqual(tree._parameters, {})

    def test_integer_feature_appears_in_parameters(self):
        tree, _, _ = make_tree(features=[_int_feature()])
        self.assertIn('Width', tree._parameters)

    def test_raises_if_camera_not_open(self):
        cam, _ = make_camera()
        cam.close()
        with self.assertRaises(RuntimeError):
            QGenicamTree(camera=cam)


# ---------------------------------------------------------------------------
# TestDescribe
# ---------------------------------------------------------------------------

class TestDescribe(unittest.TestCase):

    def setUp(self):
        self.tree, _, _ = make_tree()

    def test_describe_returns_name_and_title(self):
        f = _int_feature('Width')
        d = self.tree.describe(f)
        self.assertEqual(d['name'], 'Width')
        self.assertEqual(d['title'], 'Width')

    def test_describe_integer(self):
        f = _int_feature('Width', value=640, min=64, max=1920, inc=4)
        d = self.tree.describe(f)
        self.assertEqual(d['type'], 'int')
        self.assertEqual(d['value'], 640)
        self.assertEqual(d['default'], 640)
        self.assertEqual(d['min'], 64)
        self.assertEqual(d['max'], 1920)
        self.assertEqual(d['step'], 4)

    def test_describe_float_with_inc(self):
        f = _float_feature('Gamma', value=1.0, min=0.1, max=4.0,
                           unit='dB', has_inc=True, inc=0.1)
        d = self.tree.describe(f)
        self.assertEqual(d['type'], 'float')
        self.assertEqual(d['value'], 1.0)
        self.assertEqual(d['units'], 'dB')
        self.assertIn('step', d)
        self.assertAlmostEqual(d['step'], 0.1)

    def test_describe_float_without_inc(self):
        f = _float_feature('Gamma', has_inc=False)
        d = self.tree.describe(f)
        self.assertEqual(d['type'], 'float')
        self.assertNotIn('step', d)

    def test_describe_boolean(self):
        f = _bool_feature('ReverseX', value=False)
        d = self.tree.describe(f)
        self.assertEqual(d['type'], 'bool')
        self.assertEqual(d['value'], False)
        self.assertEqual(d['default'], False)

    def test_describe_enumeration(self):
        f = _enum_feature('PixelFormat', value='Mono8',
                          entries=('Mono8', 'RGB8'))
        d = self.tree.describe(f)
        self.assertEqual(d['type'], 'list')
        self.assertEqual(d['value'], 'Mono8')
        self.assertEqual(d['limits'], ['Mono8', 'RGB8'])

    def test_describe_string(self):
        f = _str_feature('DeviceUserID', value='cam0')
        d = self.tree.describe(f)
        self.assertEqual(d['type'], 'str')
        self.assertEqual(d['value'], 'cam0')

    def test_describe_command(self):
        f = _cmd_feature('AcquisitionStop')
        d = self.tree.describe(f)
        self.assertEqual(d['type'], 'action')
        self.assertNotIn('value', d)

    def test_describe_category_creates_group(self):
        child = _int_feature('Width')
        f = _cat_feature('ImageFormat', features=[child])
        d = self.tree.describe(f)
        self.assertEqual(d['type'], 'group')
        self.assertIn('children', d)
        self.assertEqual(len(d['children']), 1)

    def test_describe_ni_mode_omits_type(self):
        f = _int_feature('Width', mode=_EAccessMode.NI)
        d = self.tree.describe(f)
        self.assertNotIn('type', d)

    def test_describe_wo_mode_omits_type(self):
        f = _int_feature('Width', mode=_EAccessMode.WO)
        d = self.tree.describe(f)
        self.assertNotIn('type', d)

    def test_describe_stores_visibility_in_dict(self):
        f = _int_feature('Width', visibility=_EVisibility.Expert)
        d = self.tree.describe(f)
        self.assertEqual(d['visibility'], _EVisibility.Expert)


# ---------------------------------------------------------------------------
# TestVisible
# ---------------------------------------------------------------------------

class TestVisible(unittest.TestCase):

    def setUp(self):
        self.tree, _, _ = make_tree(visibility=_EVisibility.Guru)

    def _param(self, **opts):
        p = MagicMock()
        p.opts = {'visible': True, **opts}
        p.children.return_value = []
        return p

    def test_leaf_visible_when_within_level(self):
        p = self._param(type='int', visibility=_EVisibility.Beginner)
        self.assertTrue(self.tree.visible(p))

    def test_leaf_hidden_when_above_level(self):
        p = self._param(type='int', visibility=_EVisibility.Invisible)
        self.assertFalse(self.tree.visible(p))

    def test_action_type_always_hidden(self):
        p = self._param(type='action', visibility=_EVisibility.Beginner)
        self.assertFalse(self.tree.visible(p))

    def test_none_type_always_hidden(self):
        p = self._param(type=None, visibility=_EVisibility.Beginner)
        self.assertFalse(self.tree.visible(p))

    def test_group_visible_when_child_visible(self):
        child = self._param(type='int', visibility=_EVisibility.Beginner)
        group = self._param(type='group')
        group.children.return_value = [child]
        self.assertTrue(self.tree.visible(group))

    def test_group_hidden_when_all_children_hidden(self):
        child = self._param(type='int', visibility=_EVisibility.Invisible)
        group = self._param(type='group')
        group.children.return_value = [child]
        self.assertFalse(self.tree.visible(group))

    def test_no_visibility_opt_defaults_to_invisible(self):
        p = self._param(type='int')  # no 'visibility' key
        self.assertFalse(self.tree.visible(p))


# ---------------------------------------------------------------------------
# TestUpdateEnabled
# ---------------------------------------------------------------------------

class TestUpdateEnabled(unittest.TestCase):

    def test_readwrite_node_is_enabled(self):
        tree, cam, nm = make_tree(features=[_int_feature('Width')])
        # Width is in node map (has_node=True) and is_readwrite=True
        # (mode was RW during initialize).
        self.assertTrue(tree._parameters['Width'].opts.get('enabled', True))

    def test_readonly_node_is_disabled(self):
        tree, cam, nm = make_tree(
            features=[_int_feature('Width', mode=_EAccessMode.RO)])
        self.assertFalse(tree._parameters['Width'].opts.get('enabled', True))

    def test_unknown_node_does_not_log_warning(self):
        # After construction, make has_node return False for Width
        tree, cam, nm = make_tree(features=[_int_feature('Width')])
        nm.has_node.side_effect = lambda n: False
        import logging
        with self.assertNoLogs('QVideo.cameras.Genicam.QGenicamCamera',
                               level=logging.WARNING):
            tree._updateEnabled()

    def test_unknown_node_does_not_raise(self):
        tree, cam, nm = make_tree(features=[_int_feature('Width')])
        nm.has_node.side_effect = lambda n: False
        tree._updateEnabled()  # must not raise


# ---------------------------------------------------------------------------
# TestUpdateLimits
# ---------------------------------------------------------------------------

class TestUpdateLimits(unittest.TestCase):

    def test_integer_limits_updated(self):
        tree, cam, nm = make_tree(features=[_int_feature('Width',
                                                          min=64, max=1920,
                                                          inc=4)])
        # Change the node's min/max and call _updateLimits
        node = nm.get_node('Width')
        node.min = 128
        node.max = 3840
        node.inc = 8
        tree._updateLimits()
        self.assertEqual(tree._parameters['Width'].opts['limits'], (128, 3840))
        self.assertEqual(tree._parameters['Width'].opts['step'], 8)

    def test_float_limits_with_inc_updated(self):
        tree, cam, nm = make_tree(
            features=[_float_feature('Gamma', min=0.1, max=4.0,
                                     has_inc=True, inc=0.1)])
        node = nm.get_node('Gamma')
        node.min = 0.5
        node.max = 2.0
        node.inc = 0.05
        node.has_inc.return_value = True
        tree._updateLimits()
        self.assertAlmostEqual(
            tree._parameters['Gamma'].opts['limits'][0], 0.5)
        self.assertIn('step', tree._parameters['Gamma'].opts)

    def test_float_limits_without_inc_no_step(self):
        tree, cam, nm = make_tree(
            features=[_float_feature('Gamma', has_inc=False)])
        node = nm.get_node('Gamma')
        node.min = 0.5
        node.max = 2.0
        node.has_inc.return_value = False
        before_step = tree._parameters['Gamma'].opts.get('step')
        tree._updateLimits()
        # step should not appear if has_inc is False
        self.assertEqual(tree._parameters['Gamma'].opts.get('step'), before_step)

    def test_enumeration_limits_updated(self):
        tree, cam, nm = make_tree(
            features=[_enum_feature('PixelFormat', entries=('Mono8', 'RGB8'))])
        node = nm.get_node('PixelFormat')
        new_entry = MagicMock()
        new_entry.symbolic = 'BayerRG8'
        node.entries = [new_entry]
        tree._updateLimits()
        self.assertEqual(tree._parameters['PixelFormat'].opts['limits'],
                         ['BayerRG8'])

    def test_unknown_node_does_not_log_warning(self):
        tree, cam, nm = make_tree(features=[_int_feature('Width')])
        nm.has_node.side_effect = lambda n: False
        import logging
        with self.assertNoLogs('QVideo.cameras.Genicam.QGenicamCamera',
                               level=logging.WARNING):
            tree._updateLimits()

    def test_unknown_node_does_not_raise(self):
        tree, cam, nm = make_tree(features=[_int_feature('Width')])
        nm.has_node.side_effect = lambda n: False
        tree._updateLimits()  # must not raise


# ---------------------------------------------------------------------------
# TestControls
# ---------------------------------------------------------------------------

class TestControls(unittest.TestCase):

    def test_controls_none_preserves_natural_visibility(self):
        features = [_int_feature('Width', visibility=_EVisibility.Beginner),
                    _int_feature('Height', visibility=_EVisibility.Expert)]
        tree, _, _ = make_tree(features=features, controls=None)
        # Both are within Guru level → both visible
        p_w = tree._parameters['Width']
        p_h = tree._parameters['Height']
        self.assertTrue(p_w.opts.get('visible', False))
        self.assertTrue(p_h.opts.get('visible', False))

    def test_controls_list_hides_unlisted_params(self):
        features = [_int_feature('Width'), _int_feature('Height')]
        # Set controls to ['Width'] only — Height should become invisible
        tree, cam, nm = make_tree(features=features, controls=['Width'])
        # After controls setter, Height gets EVisibility.Invisible
        p_h = tree._parameters['Height']
        self.assertEqual(p_h.opts.get('visibility'), _EVisibility.Invisible)

    def test_controls_list_keeps_listed_param_visibility(self):
        features = [_int_feature('Width', visibility=_EVisibility.Beginner)]
        tree, cam, nm = make_tree(features=features, controls=['Width'])
        p_w = tree._parameters['Width']
        self.assertEqual(p_w.opts.get('visibility'), _EVisibility.Beginner)

    def test_controls_node_returns_none_does_not_crash(self):
        features = [_int_feature('Width')]
        tree, cam, nm = make_tree(features=features)
        # Simulate node becoming unavailable
        nm.get_node.side_effect = lambda n: None
        tree.controls = ['Width']  # must not raise


# ---------------------------------------------------------------------------
# TestVisibilityProperty
# ---------------------------------------------------------------------------

class TestVisibilityProp(unittest.TestCase):

    def test_default_visibility_is_guru(self):
        tree, _, _ = make_tree()
        self.assertEqual(tree.visibility, _EVisibility.Guru)

    def test_beginner_level_hides_expert_nodes(self):
        features = [
            _int_feature('Width',   visibility=_EVisibility.Beginner),
            _int_feature('OffsetX', visibility=_EVisibility.Expert),
        ]
        tree, _, _ = make_tree(features=features)
        tree.visibility = _EVisibility.Beginner
        # OffsetX is Expert (1) > Beginner (0) → hidden
        p_offset = tree._parameters['OffsetX']
        self.assertFalse(p_offset.opts.get('visible', True))

    def test_guru_level_shows_expert_nodes(self):
        features = [_int_feature('OffsetX', visibility=_EVisibility.Expert)]
        tree, _, _ = make_tree(features=features, visibility=_EVisibility.Beginner)
        tree.visibility = _EVisibility.Guru
        p_offset = tree._parameters['OffsetX']
        self.assertTrue(p_offset.opts.get('visible', False))

    def test_setting_visibility_stores_value(self):
        tree, _, _ = make_tree()
        tree.visibility = _EVisibility.Expert
        self.assertEqual(tree.visibility, _EVisibility.Expert)


if __name__ == '__main__':
    unittest.main()
