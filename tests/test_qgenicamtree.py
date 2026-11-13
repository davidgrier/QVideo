'''Unit tests for QGenicamTree.'''
import sys
import unittest
from unittest.mock import MagicMock, PropertyMock, patch
from qtpy import QtCore, QtWidgets


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
class _IRegister(_IValue):    pass


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
        mock_genapi.IRegister    = _IRegister
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

# Remove any MagicMock stub for _tree so the real class is loaded.
for _key in list(sys.modules):
    if 'Genicam._tree' in _key:
        del sys.modules[_key]

from QVideo.cameras.Genicam._camera import QGenicamCamera  # noqa: E402
from QVideo.cameras.Genicam._tree import QGenicamTree      # noqa: E402

_cam_module  = sys.modules['QVideo.cameras.Genicam._camera']
_nodes_module = sys.modules['QVideo.cameras.Genicam._nodes']
_tree_module = sys.modules['QVideo.cameras.Genicam._tree']

# Use the exact class objects that the loaded modules reference.
_ICategory    = _nodes_module.ICategory
_ICommand     = _nodes_module.ICommand
_IEnumeration = _nodes_module.IEnumeration
_IBoolean     = _nodes_module.IBoolean
_IInteger     = _nodes_module.IInteger
_IFloat       = _nodes_module.IFloat
_IString      = _nodes_module.IString
_IRegister    = _nodes_module.IRegister
_EAccessMode  = _cam_module.EAccessMode
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
        self.cam, _ = make_camera()
        self.tree = self.cam

    def test_describe_returns_name_and_title(self):
        f = _int_feature('Width')
        d = _nodes_module.describe(f)
        self.assertEqual(d['name'], 'Width')
        self.assertEqual(d['title'], 'Width')

    def test_describe_integer(self):
        f = _int_feature('Width', value=640, min=64, max=1920, inc=4)
        d = _nodes_module.describe(f)
        self.assertEqual(d['type'], 'int')
        self.assertEqual(d['value'], 640)
        self.assertEqual(d['default'], 640)
        self.assertEqual(d['min'], 64)
        self.assertEqual(d['max'], 1920)
        self.assertEqual(d['step'], 4)

    def test_describe_float_with_inc(self):
        f = _float_feature('Gamma', value=1.0, min=0.1, max=4.0,
                           unit='dB', has_inc=True, inc=0.1)
        d = _nodes_module.describe(f)
        self.assertEqual(d['type'], 'float')
        self.assertEqual(d['value'], 1.0)
        self.assertEqual(d['unit'], 'dB')
        self.assertAlmostEqual(d['step'], 0.1)

    def test_describe_float_without_inc(self):
        f = _float_feature('Gamma', has_inc=False)
        d = _nodes_module.describe(f)
        self.assertEqual(d['type'], 'float')
        self.assertNotIn('step', d)

    def test_describe_boolean(self):
        f = _bool_feature('ReverseX', value=False)
        d = _nodes_module.describe(f)
        self.assertEqual(d['type'], 'bool')
        self.assertEqual(d['value'], False)
        self.assertEqual(d['default'], False)

    def test_describe_enumeration(self):
        f = _enum_feature('PixelFormat', value='Mono8',
                          entries=('Mono8', 'RGB8'))
        d = _nodes_module.describe(f)
        self.assertEqual(d['type'], 'list')
        self.assertEqual(d['value'], 'Mono8')
        self.assertEqual(d['limits'], ['Mono8', 'RGB8'])

    def test_describe_string(self):
        f = _str_feature('DeviceUserID', value='cam0')
        d = _nodes_module.describe(f)
        self.assertEqual(d['type'], 'str')
        self.assertEqual(d['value'], 'cam0')

    def test_describe_register_is_read_only_text(self):
        f = _make_feature(_IRegister, 'UserData', length=2, address=0)
        f.get.return_value = b'\x01\x02'
        d = _nodes_module.describe(f)
        self.assertEqual(d['type'], 'str')
        self.assertEqual(d['value'], '01 02')
        self.assertTrue(d['readonly'])

    def test_describe_command(self):
        f = _cmd_feature('AcquisitionStop')
        d = _nodes_module.describe(f)
        self.assertEqual(d['type'], 'action')
        self.assertNotIn('value', d)

    def test_describe_category_creates_group(self):
        child = _int_feature('Width')
        f = _cat_feature('ImageFormat', features=[child])
        d = _nodes_module.describe(f)
        self.assertEqual(d['type'], 'group')
        self.assertIn('children', d)
        self.assertEqual(len(d['children']), 1)

    def test_describe_ni_mode_omits_type(self):
        f = _int_feature('Width', mode=_EAccessMode.NI)
        d = _nodes_module.describe(f)
        self.assertNotIn('type', d)

    def test_describe_wo_mode_omits_type(self):
        f = _int_feature('Width', mode=_EAccessMode.WO)
        d = _nodes_module.describe(f)
        self.assertNotIn('type', d)

    def test_describe_stores_visibility_in_dict(self):
        f = _int_feature('Width', visibility=_EVisibility.Expert)
        d = _nodes_module.describe(f)
        self.assertEqual(d['visibility'], _EVisibility.Expert)


class TestScaledWrites(unittest.TestCase):

    '''A control in seconds is a node in microseconds: the hooks convert.'''

    def setUp(self):
        features = [_float_feature('ExposureTime', value=10000., min=10.,
                                   max=1e6, unit='us'),
                    _float_feature('Gamma', value=1.0)]
        self.tree, self.cam, _ = make_tree(features=features)
        self.addCleanup(self.tree.stop)

    def test_the_value_goes_to_the_camera_in_the_units_of_the_node(self):
        self.assertAlmostEqual(self.tree._toCamera('ExposureTime', 0.002),
                               2000.)

    def test_a_node_without_a_scale_is_sent_as_it_is(self):
        self.assertEqual(self.tree._toCamera('Gamma', 2.0), 2.0)

    def test_the_value_comes_back_in_the_units_of_the_control(self):
        self.assertAlmostEqual(self.tree._fromCamera('ExposureTime', 2000.),
                               0.002)
        self.assertEqual(self.tree._fromCamera('Gamma', 2.0), 2.0)

    def test_the_readback_is_all_of_the_settings(self):
        with patch.object(type(self.cam), 'settings',
                          new_callable=PropertyMock,
                          return_value={'Gamma': 1.5}):
            self.assertEqual(self.tree._readback(), {'Gamma': 1.5})

    def test_the_others_are_not_told(self):
        heard = []
        self.cam.propertiesChanged.connect(
            lambda values: heard.append(values),
            QtCore.Qt.ConnectionType.DirectConnection)
        self.tree._announce({'Gamma': 1.5})
        self.assertEqual(heard, [])

    def test_an_edit_goes_in_microseconds_and_comes_back_in_seconds(self):
        settings = {'ExposureTime': 2000., 'Gamma': 1.0}
        with patch.object(type(self.cam), 'settings',
                          new_callable=PropertyMock, return_value=settings), \
                patch.object(self.cam, 'set') as set_:
            self.tree._parameters['ExposureTime'].setValue(0.002)
            self.assertTrue(self.tree.flush())
        key, sent = set_.call_args.args
        self.assertEqual(key, 'ExposureTime')
        self.assertAlmostEqual(sent, 2000.)
        self.assertAlmostEqual(self.tree._parameters['ExposureTime'].value(),
                               0.002)


class TestSliders(unittest.TestCase):

    '''A node that holds a number with a range is a slider with a spin box.'''

    def setUp(self):
        self.tree, _, _ = make_tree()

    def node(self, **kw):
        this = dict(name='N', title='N', visibility=0, type='int', value=5,
                    default=5, min=0, max=100)
        this.update(kw)
        return self.tree.describe(this)

    def test_a_whole_number_with_a_range_is_a_slider(self):
        d = self.node()
        self.assertEqual(d['type'], 'sliderspin')
        self.assertTrue(d['int'])

    def test_a_real_number_with_a_range_is_a_slider_in_the_units_of_the_tree(
            self):
        d = self.node(type='float', value=10000., default=10000., min=10.,
                      max=1e6, unit='us', step=1.)
        self.assertEqual(d['type'], 'sliderspin')
        self.assertFalse(d['int'])
        self.assertEqual(d['units'], 's')                    # not us
        self.assertAlmostEqual(d['max'], 1.)
        self.assertAlmostEqual(d['value'], 0.01)

    def test_a_number_without_a_range_is_as_before(self):
        self.assertEqual(self.node(min=None, max=None)['type'], 'int')
        # and a node that does not even have the keys
        self.assertEqual(self.tree.describe(
            dict(name='M', title='M', visibility=0, type='int', value=1,
                 default=1))['type'], 'int')

    def test_a_range_of_one_point_is_as_before(self):
        self.assertEqual(self.node(min=5, max=5)['type'], 'int')

    def test_a_range_that_is_not_finite_is_as_before(self):
        self.assertEqual(self.node(min=0., max=float('inf'),
                                   type='float', unit='')['type'], 'float')

    def test_a_range_of_billions_has_no_slider(self):
        self.assertEqual(self.node(min=0, max=2 ** 32)['type'], 'int')

    def test_a_register_is_as_before(self):
        self.assertEqual(self.node(readonly=True)['type'], 'int')

    def test_other_types_are_as_before(self):
        for kind in ('list', 'bool', 'str', 'action'):
            with self.subTest(kind=kind):
                self.assertEqual(self.node(type=kind)['type'], kind)

    def test_the_tree_builds_sliders(self):
        features = [_int_feature('Width', value=1280, min=128, max=3840,
                                 inc=8),
                    _float_feature('Gamma', value=1., min=0.1, max=4.)]
        tree, _, _ = make_tree(features=features)
        self.assertEqual(tree._parameters['Width'].opts['type'], 'sliderspin')
        self.assertEqual(tree._parameters['Gamma'].opts['type'], 'sliderspin')

    def test_the_range_of_the_control_follows_the_camera(self):
        features = [_int_feature('Width', value=1280, min=128, max=3840,
                                 inc=8)]
        tree, cam, nm = make_tree(features=features)
        widget = next(iter(tree._parameters['Width'].items)).widget
        self.assertEqual((widget.minimum, widget.maximum), (128, 3840))
        node = nm.get_node('Width')
        node.min, node.max = 128, 2000          # another setting narrowed it
        tree._updateLimits()
        self.assertEqual((widget.minimum, widget.maximum), (128, 2000))
        self.assertEqual(widget.value(), 1280)


class TestConvert(unittest.TestCase):
    '''The tree turns the plain description of the camera into parameters.'''

    def setUp(self):
        self.tree, _, _ = make_tree()

    def _float(self, **kw):
        return dict(name='ExposureTime', title='ExposureTime', visibility=0,
                    type='float', value=10000., default=10000., min=10.,
                    max=1e6, unit='us', **kw)

    def test_microseconds_become_seconds(self):
        d = self.tree.describe(dict(self._float(step=1.), max=500.))
        self.assertEqual(d['units'], 's')
        self.assertTrue(d['siPrefix'])
        self.assertAlmostEqual(d['value'], 0.01)
        self.assertAlmostEqual(d['max'], 5e-4)
        self.assertAlmostEqual(d['step'], 1e-6)
        self.assertEqual(self.tree._scaleFactors['ExposureTime'], 1e-6)

    def test_wide_range_is_stepped_by_decades(self):
        d = self.tree.describe(self._float())
        self.assertIn('ExposureTime', self.tree._decParams)
        self.assertAlmostEqual(d['step'], 1e-3)

    def test_float_without_step_has_none(self):
        d = self.tree.describe(dict(self._float(), unit='dB', min=1., max=2.))
        self.assertNotIn('step', d)
        self.assertEqual(d['units'], 'dB')

    def test_names_and_visibilities_are_recorded(self):
        self.tree.describe(dict(name='G', title='G', visibility=1,
                                type='group', children=[
                                    dict(name='W', title='W', visibility=2,
                                         type='int')]))
        self.assertEqual(self.tree._visibilities['G'], 1)
        self.assertEqual(self.tree._visibilities['W'], 2)


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
        # Width is in the node map and was RW during initialize.
        self.assertTrue(tree._parameters['Width'].opts.get('enabled', True))

    def test_readonly_node_is_disabled(self):
        tree, cam, nm = make_tree(
            features=[_int_feature('Width', mode=_EAccessMode.RO)])
        self.assertFalse(tree._parameters['Width'].opts.get('enabled', True))


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


# ---------------------------------------------------------------------------
# TestShowChanges
# ---------------------------------------------------------------------------

class TestShowChanges(unittest.TestCase):
    '''The tree refreshes when the camera reports that it changed.'''

    def make(self, n=5):
        features = [_float_feature(f'F{i}', value=1.0) for i in range(n)]
        return make_tree(features=features)

    def test_a_report_asks_the_camera_once_for_every_shown_node(self):
        tree, cam, _ = self.make()
        with patch.object(cam, 'states', wraps=cam.states) as states:
            tree._showChanges({'F0': 2.0})
            tree.flush()
        self.assertEqual(states.call_count, 1)
        self.assertEqual(len(list(states.call_args[0][0])), 5)

    def test_values_that_the_camera_changed_are_shown(self):
        tree, cam, nm = self.make()
        for i in range(5):
            nm.get_node(f'F{i}').value = 2.0
        tree._showChanges({'F0': 2.0})
        tree.flush()
        for i in range(5):
            self.assertAlmostEqual(tree._parameters[f'F{i}'].value(), 2.0)

    def test_nothing_is_sent_back_to_the_camera(self):
        tree, cam, nm = self.make()
        nm.get_node('F0').value = 2.0
        with patch.object(cam, 'set') as send:
            tree._showChanges({'F0': 2.0})
            tree.flush()
        send.assert_not_called()

    def test_a_closed_camera_is_left_alone(self):
        tree, cam, _ = self.make()
        cam.close()
        with patch.object(cam, 'states') as states:
            tree._showChanges({})
            tree.flush()
        states.assert_not_called()

    def test_the_camera_signal_reaches_the_tree(self):
        tree, cam, nm = self.make()
        nm.get_node('F1').value = 3.0
        cam.propertiesChanged.emit({'F1': 3.0})
        tree.flush()
        self.assertAlmostEqual(tree._parameters['F1'].value(), 3.0)

    def test_a_change_of_a_property_reads_everything_at_once(self):
        tree, cam, _ = self.make()
        with patch.object(cam, 'states', wraps=cam.states) as states:
            tree._handleItemChanges()
            tree.flush()
        self.assertEqual(states.call_count, 1)
        self.assertEqual(len(list(states.call_args[0][0])), 5)

    def test_no_timer_polls_the_camera(self):
        tree, _, _ = self.make()
        self.assertFalse(hasattr(tree, '_timer'))


# ---------------------------------------------------------------------------
# TestUpdateValues
# ---------------------------------------------------------------------------

class TestUpdateValues(unittest.TestCase):

    def test_ro_float_value_is_refreshed(self):
        feat = _float_feature('ResultFPS', value=30.0, mode=_EAccessMode.RO)
        tree, cam, nm = make_tree(features=[feat])
        nm.get_node('ResultFPS').value = 60.0
        tree._updateValues()
        self.assertAlmostEqual(tree._parameters['ResultFPS'].value(), 60.0)

    def test_ro_integer_value_is_refreshed(self):
        feat = _int_feature('Width', value=640, mode=_EAccessMode.RO)
        tree, cam, nm = make_tree(features=[feat])
        nm.get_node('Width').value = 1280
        tree._updateValues()
        self.assertEqual(tree._parameters['Width'].value(), 1280)

    def test_ro_enumeration_value_is_refreshed(self):
        feat = _enum_feature('PixelFormat', value='Mono8',
                             entries=('Mono8', 'RGB8'), mode=_EAccessMode.RO)
        tree, cam, nm = make_tree(features=[feat])
        nm.get_node('PixelFormat').to_string.return_value = 'RGB8'
        tree._updateValues()
        self.assertEqual(tree._parameters['PixelFormat'].value(), 'RGB8')

    def test_rw_node_value_not_refreshed_by_update(self):
        feat = _float_feature('Gamma', value=1.0, mode=_EAccessMode.RW)
        tree, cam, nm = make_tree(features=[feat])
        nm.get_node('Gamma').value = 2.0
        tree._updateValues()
        self.assertAlmostEqual(tree._parameters['Gamma'].value(), 1.0)

    def test_rw_node_value_refreshed_by_a_report(self):
        feat = _float_feature('Gamma', value=1.0, mode=_EAccessMode.RW)
        tree, cam, nm = make_tree(features=[feat])
        nm.get_node('Gamma').value = 2.0
        tree._showChanges({'Gamma': 2.0})
        tree.flush()
        self.assertAlmostEqual(tree._parameters['Gamma'].value(), 2.0)

    def test_invisible_node_skipped(self):
        feat = _float_feature('ResultFPS', value=1.5, min=0.5, max=120.0,
                              mode=_EAccessMode.RO,
                              visibility=_EVisibility.Invisible)
        tree, cam, nm = make_tree(features=[feat])
        nm.get_node('ResultFPS').value = 3.0
        tree._updateValues()
        self.assertAlmostEqual(tree._parameters['ResultFPS'].value(), 1.5)


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

    def test_controls_change_at_runtime_updates_visible_state(self):
        features = [_int_feature('Width'), _int_feature('Height')]
        tree, _, _ = make_tree(features=features)
        # Both visible initially; restrict to Width only
        tree.controls = ['Width']
        p_h = tree._parameters['Height']
        self.assertFalse(p_h.opts.get('visible', True))


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

class TestReadsInAWorker(unittest.TestCase):
    '''The camera lock is held while the camera waits for a frame, so the
    tree reads the nodes in a thread of its own, never in the interface.'''

    def make(self):
        return make_tree(features=[_float_feature(f'F{i}', value=1.0)
                                   for i in range(3)])

    def test_the_nodes_are_not_read_in_the_interface_thread(self):
        import threading
        tree, cam, _ = self.make()
        threads = []
        real = cam.states

        def states(names):
            threads.append(threading.current_thread())
            return real(names)

        with patch.object(cam, 'states', states):
            tree._showChanges({'F0': 2.0})
            tree._handleItemChanges()
            tree.flush()
        self.assertTrue(threads)
        self.assertNotIn(threading.main_thread(), threads)

    def test_requests_that_pile_up_are_read_once_or_twice(self):
        import threading
        tree, cam, _ = self.make()
        gate, entered = threading.Event(), threading.Event()
        real = cam.states
        count = []

        def states(names):
            count.append(1)
            entered.set()
            gate.wait(5)
            return real(names)

        with patch.object(cam, 'states', states):
            tree._showChanges({})
            entered.wait(5)
            for _ in range(20):
                tree._showChanges({})
            gate.set()
            tree.flush()
        self.assertLessEqual(len(count), 2)

    def test_a_request_for_the_values_is_not_lost_to_a_later_one(self):
        tree, cam, nm = self.make()
        nm.get_node('F0').value = 2.0
        tree._showChanges({'F0': 2.0})      # asks for the values
        tree._handleItemChanges()           # does not
        tree.flush()
        self.assertAlmostEqual(tree._parameters['F0'].value(), 2.0)

    def test_a_control_that_was_changed_since_is_not_overwritten(self):
        tree, cam, nm = self.make()
        nm.get_node('F0').value = 2.0
        tree._edits['F0'] = 1               # the user changed it; not written
        tree._showChanges({'F0': 2.0})
        tree.flush()
        self.assertAlmostEqual(tree._parameters['F0'].value(), 1.0)

    def test_an_item_change_does_not_show_the_values_of_the_camera(self):
        tree, cam, nm = self.make()
        nm.get_node('F0').value = 2.0
        tree._handleItemChanges()
        tree.flush()
        self.assertAlmostEqual(tree._parameters['F0'].value(), 1.0)

    def test_a_tree_that_is_not_threaded_reads_at_once(self):
        cam, nm = make_camera([_float_feature('F0', value=1.0)])
        tree = QGenicamTree(camera=cam, visibility=_EVisibility.Guru,
                            threaded=False)
        nm.get_node('F0').value = 2.0
        tree._showChanges({'F0': 2.0})
        self.assertAlmostEqual(tree._parameters['F0'].value(), 2.0)
        self.assertTrue(tree.flush())



class TestShowingRows(unittest.TestCase):
    '''Showing and hiding rows does not read the camera again.'''

    def test_hiding_rows_reads_no_settings(self):
        features = [_float_feature(f'F{i}', value=1.0) for i in range(5)]
        tree, cam, _ = make_tree(features=features)
        with patch.object(type(cam), 'settings',
                          new_callable=PropertyMock) as settings:
            tree.controls = ['F0']
            tree.visibility = tree.visibility
        settings.assert_not_called()

    def test_the_sync_is_restored(self):
        tree, _, _ = make_tree(features=[_float_feature('F0', value=1.)])
        tree._updateVisible()
        self.assertFalse(tree._ignoreSync)
