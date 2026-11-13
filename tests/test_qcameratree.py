'''Unit tests for QCameraTree.'''
import threading
import time
import unittest
from unittest.mock import patch, MagicMock
from qtpy import QtCore, QtGui, QtWidgets
from QVideo.lib.QCameraTree import QCameraTree
from QVideo.lib.QCamera import PropertySpec
from QVideo.cameras.Noise._camera import QNoiseCamera
from QVideo.lib import QVideoSource


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def make_camera():
    return QNoiseCamera()


def make_source(camera=None):
    camera = camera or make_camera()
    return QVideoSource(camera)


def make_tree(source=None):
    source = source or make_source()
    return QCameraTree(source)


class TestQCameraTreeInit(unittest.TestCase):

    def test_raises_if_source_not_open(self):
        cam = make_camera()
        cam.close()
        source = QVideoSource(cam)
        with self.assertRaises(RuntimeError):
            QCameraTree(source)

    def test_creates_successfully_with_open_source(self):
        tree = make_tree()
        self.assertIsInstance(tree, QCameraTree)

    def test_the_tree_has_no_header_by_default(self):
        self.assertTrue(make_tree().isHeaderHidden())

    def test_the_header_can_be_asked_for(self):
        tree = QCameraTree(make_source(), showHeader=True)
        self.assertFalse(tree.isHeaderHidden())

    def test_camera_property_returns_noise_camera(self):
        cam = make_camera()
        tree = make_tree(source=make_source(cam))
        self.assertIs(tree.camera, cam)

    def test_source_property_returns_source(self):
        source = make_source()
        tree = QCameraTree(source)
        self.assertIs(tree.source, source)

    def test_accepts_bare_camera(self):
        cam = make_camera()
        tree = QCameraTree(cam)
        self.assertIsInstance(tree, QCameraTree)


class TestQCameraTreeTitle(unittest.TestCase):

    def test_title_uses_class_name_when_model_name_is_none(self):
        cam = make_camera()
        self.assertIsNone(cam.model_name)
        tree = make_tree(source=make_source(cam))
        self.assertEqual(tree._tree.name(), cam.name)

    def test_title_uses_model_name_when_set(self):
        cam = make_camera()
        cam._modelName = 'FaceTime HD Camera'
        tree = make_tree(source=make_source(cam))
        self.assertEqual(tree._tree.name(), 'FaceTime HD Camera')

    def test_title_falls_back_to_class_name_for_empty_model_name(self):
        cam = make_camera()
        cam._modelName = ''
        tree = make_tree(source=make_source(cam))
        self.assertEqual(tree._tree.name(), cam.name)


class TestQCameraTreeDefaultDescription(unittest.TestCase):

    def test_all_camera_properties_appear_in_tree(self):
        cam = make_camera()
        tree = make_tree(source=make_source(cam))
        for name in cam.properties:
            self.assertIn(name, tree._parameters)

    def test_readonly_property_is_disabled_in_tree(self):
        '''QNoiseCamera.color has setter=None and should appear disabled.'''
        tree = make_tree()
        color_param = tree._parameters.get('color')
        self.assertIsNotNone(color_param)
        self.assertFalse(color_param.opts.get('enabled', True))

    def test_writable_property_is_enabled_in_tree(self):
        tree = make_tree()
        width_param = tree._parameters.get('width')
        self.assertIsNotNone(width_param)
        self.assertTrue(width_param.opts.get('enabled', True))


class TestQCameraTreeChoiceProperty(unittest.TestCase):
    '''A string property with ``limits`` becomes a list control.'''

    def _camera(self):
        cam = make_camera()
        self.mode = 'fast'

        def setMode(value):
            self.mode = value
        cam.registerProperty('mode', getter=lambda: self.mode,
                             setter=setMode, ptype=str,
                             limits=['fast', 'slow'])
        cam.registerProperty('plain', getter=lambda: 'abc',
                             setter=lambda v: None, ptype=str)
        cam.registerProperty('count', getter=lambda: 3,
                             setter=lambda v: None, ptype=int,
                             limits=(0, 10))
        return cam

    def _entry(self, name):
        desc = QCameraTree._defaultDescription(self._camera())
        return next(d for d in desc if d['name'] == name)

    def test_string_property_with_limits_is_a_list(self):
        entry = self._entry('mode')
        self.assertEqual(entry['type'], 'list')
        self.assertEqual(entry['limits'], ['fast', 'slow'])
        self.assertEqual(entry['value'], 'fast')

    def test_string_property_without_limits_stays_a_string(self):
        self.assertEqual(self._entry('plain')['type'], 'str')
        self.assertNotIn('limits', self._entry('plain'))

    def test_numeric_limits_are_not_turned_into_a_list(self):
        self.assertEqual(self._entry('count')['type'], 'int')

    def test_selecting_an_entry_sets_the_camera_property(self):
        tree = QCameraTree(make_source(self._camera()))
        tree._parameters['mode'].setValue('slow')
        tree.flush()
        self.assertEqual(self.mode, 'slow')

    def test_unrelated_change_does_not_reset_the_selection(self):
        tree = QCameraTree(make_source(self._camera()))
        tree._parameters['mode'].setValue('slow')
        param = MagicMock()
        param.name.return_value = 'plain'
        tree._sync(None, [(param, 'value', 'xyz')])
        self.assertEqual(tree._parameters['mode'].value(), 'slow')


class TestQCameraTreeGet(unittest.TestCase):

    def test_get_returns_current_value(self):
        cam = make_camera()
        tree = make_tree(source=make_source(cam))
        self.assertEqual(tree.get('width'), cam.width)

    def test_get_unknown_key_returns_none(self):
        tree = make_tree()
        with self.assertLogs('QVideo.lib.QCameraTree', level='WARNING'):
            result = tree.get('nonexistent')
        self.assertIsNone(result)


class TestQCameraTreeSet(unittest.TestCase):

    def test_set_updates_tree_parameter(self):
        cam = make_camera()
        tree = make_tree(source=make_source(cam))
        tree.set('width', 320)
        self.assertEqual(tree._parameters['width'].value(), 320)

    def test_set_unknown_key_logs_warning(self):
        tree = make_tree()
        with self.assertLogs('QVideo.lib.QCameraTree', level='WARNING'):
            tree.set('nonexistent', 42)


class TestQCameraTreeSync(unittest.TestCase):

    def test_tree_change_updates_camera(self):
        '''Changing a parameter in the tree calls camera.set().'''
        cam = make_camera()
        tree = make_tree(source=make_source(cam))
        tree._parameters['width'].setValue(320)
        tree.flush()
        self.assertEqual(cam.width, 320)

    def test_a_change_in_the_tree_is_announced_to_the_others(self):
        '''A web page that shows the camera hears what the tree changed.'''
        cam = make_camera()
        tree = make_tree(source=make_source(cam))
        heard = []
        # The camera lives in the thread of its source: a direct connection
        # is the only one that PySide6 delivers to a function in this test.
        cam.propertiesChanged.connect(
            lambda values: heard.append(values),
            QtCore.Qt.ConnectionType.DirectConnection)
        tree._parameters['width'].setValue(320)
        tree.flush()
        self.assertEqual(len(heard), 1)
        self.assertEqual(heard[0]['width'], 320)

    def test_set_does_not_cause_infinite_loop(self):
        '''_sync sets _ignoreSync to avoid re-entrant loops.'''
        tree = make_tree()
        # If this call returns without recursion error, the guard works
        tree._parameters['width'].setValue(320)
        tree.flush()


class TestQCameraTreeSyncReadsWhatItShows(unittest.TestCase):
    '''After a change the tree reads back its own properties only.

    A camera has many more properties than a tree has controls (viva-genicam
    on a Blackfly S: about 2000 and 15); reading them all took a register
    read each and logged a warning for each that the tree does not show.
    '''

    def camera_with_hidden_property(self):
        cam = make_camera()
        unseen = MagicMock(return_value=1.)
        cam.registerProperty('unseen', getter=unseen, setter=None,
                             ptype=float)
        return cam, unseen

    def test_a_property_that_the_tree_does_not_show_is_not_read(self):
        cam, unseen = self.camera_with_hidden_property()
        desc = [{'name': 'width', 'type': 'int', 'value': 640,
                 'default': 640}]
        tree = QCameraTree(make_source(cam), description=desc)
        unseen.reset_mock()
        tree._parameters['width'].setValue(320)
        tree.flush()
        unseen.assert_not_called()

    def test_it_logs_no_warning_for_a_property_that_it_does_not_show(self):
        cam, _ = self.camera_with_hidden_property()
        desc = [{'name': 'width', 'type': 'int', 'value': 640,
                 'default': 640}]
        tree = QCameraTree(make_source(cam), description=desc)
        with self.assertNoLogs('QVideo.lib.QCameraTree', 'WARNING'):
            tree._parameters['width'].setValue(320)
            tree.flush()

    def test_an_entry_that_is_not_a_camera_property_does_no_harm(self):
        desc = [{'name': 'width', 'type': 'int', 'value': 640,
                 'default': 640},
                {'name': 'note', 'type': 'str', 'value': 'x'}]
        tree = QCameraTree(make_source(), description=desc)
        tree._parameters['width'].setValue(320)
        tree.flush()
        self.assertEqual(tree.get('note'), 'x')

    def test_a_value_that_cannot_be_read_now_stays_in_the_tree(self):
        cam = make_camera()
        tree = make_tree(source=make_source(cam))
        tree._parameters['height'].setValue(300)
        tree.flush()
        cam.properties['height']['getter'] = lambda: None
        tree._parameters['width'].setValue(320)       # triggers the readback
        tree.flush()
        self.assertEqual(tree.get('height'), 300)

    def test_the_tree_shows_what_the_camera_did_beyond_the_request(self):
        cam = make_camera()
        tree = make_tree(source=make_source(cam))
        cam._height = 100                              # the camera did this
        tree._parameters['width'].setValue(320)
        tree.flush()
        self.assertEqual(tree.get('height'), 100)


class TestQCameraTreeLost(unittest.TestCase):
    '''The controls of a camera that was lost are disabled.'''

    def setUp(self):
        self.tree = make_tree()
        self.addCleanup(self.tree.stop)

    def lose(self, reason='unplugged'):
        with self.assertLogs('QVideo.lib.QCamera', 'ERROR'):
            self.tree.camera._deviceLost(reason)
        app.processEvents()

    def test_it_is_enabled_at_first(self):
        self.assertTrue(self.tree.isEnabled())

    def test_the_loss_disables_it(self):
        self.lose()
        self.assertFalse(self.tree.isEnabled())

    def test_the_tooltip_says_why(self):
        self.lose('the cable was pulled')
        self.assertIn('the cable was pulled', self.tree.toolTip())

    def test_a_change_made_before_the_loss_still_reaches_the_camera(self):
        self.tree.set('width', 320)
        self.tree.flush()
        self.assertEqual(self.tree.camera.get('width'), 320)


class TestQCameraTreeLogging(unittest.TestCase):

    def test_the_logger_leaves_its_level_to_the_application(self):
        # A level of its own would hide the debug messages of this module
        # when an application asks for those of QVideo.
        import logging
        self.assertEqual(logging.getLogger('QVideo.lib.QCameraTree').level,
                         logging.NOTSET)


class TestSyncIgnored(unittest.TestCase):
    '''The tree stops listening while the camera sets its parameters.'''

    def test_the_tree_ignores_changes_inside_the_block(self):
        tree = make_tree()
        with tree._syncIgnored():
            self.assertTrue(tree._ignoreSync)
        self.assertFalse(tree._ignoreSync)

    def test_the_tree_listens_again_after_an_error(self):
        tree = make_tree()
        with self.assertRaises(ValueError):
            with tree._syncIgnored():
                raise ValueError('the camera failed')
        self.assertFalse(tree._ignoreSync)

    def test_blocks_nest(self):
        tree = make_tree()
        with tree._syncIgnored():
            with tree._syncIgnored():
                pass
            self.assertTrue(tree._ignoreSync)
        self.assertFalse(tree._ignoreSync)

    def test_a_camera_that_fails_does_not_silence_the_tree(self):
        cam = make_camera()
        tree = make_tree(source=make_source(cam))
        with patch.object(type(tree), 'set', side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                tree._show({'width': 5}, {})
        self.assertFalse(tree._ignoreSync)


class TestQCameraTreeDefaultDescriptionNone(unittest.TestCase):

    def test_skips_properties_with_none_getter(self):
        '''_defaultDescription omits entries whose getter returns None.'''
        cam = make_camera()
        cam.properties['_fake'] = PropertySpec(lambda: None, None)
        try:
            desc = QCameraTree._defaultDescription(cam)
            names = [e['name'] for e in desc]
            self.assertNotIn('_fake', names)
        finally:
            del cam.properties['_fake']


class TestQCameraTreeCloseEvent(unittest.TestCase):

    def test_close_event_stops_running_source(self):
        tree = make_tree()
        tree.start()
        event = QtGui.QCloseEvent()
        tree.closeEvent(event)
        self.assertFalse(tree.source.isRunning())

    def test_close_event_safe_when_not_running(self):
        tree = make_tree()
        event = QtGui.QCloseEvent()
        tree.closeEvent(event)  # should not raise


class TestQCameraTreeSyncGuard(unittest.TestCase):

    def test_sync_returns_early_when_ignoreSync_set(self):
        '''_sync short-circuits when _ignoreSync is True.'''
        cam = make_camera()
        tree = make_tree(source=make_source(cam))
        tree._ignoreSync = True
        original_width = cam.width
        # Calling _sync directly with a value change should be ignored
        param = tree._parameters['width']
        tree._sync(None, [(param, 'value', 9999)])
        tree.flush()
        self.assertEqual(cam.width, original_width)
        tree._ignoreSync = False


class TestQCameraTreeCustomDescription(unittest.TestCase):

    def test_accepts_custom_description(self):
        '''Passing a description skips _defaultDescription (covers 99→101 branch).'''
        desc = [{'name': 'width', 'type': 'int', 'value': 640, 'default': 640}]
        source = make_source()
        tree = QCameraTree(source, description=desc)
        self.assertIn('width', tree._parameters)

    def test_custom_description_excludes_undescribed_properties(self):
        desc = [{'name': 'width', 'type': 'int', 'value': 640, 'default': 640}]
        source = make_source()
        tree = QCameraTree(source, description=desc)
        self.assertNotIn('height', tree._parameters)


class TestQCameraTreeSyncNonValueChange(unittest.TestCase):

    def test_sync_ignores_non_value_changes(self):
        '''_sync skips changes where change != "value" (covers 129→128 branch).'''
        cam = make_camera()
        tree = make_tree(source=make_source(cam))
        original_width = cam.width
        param = tree._parameters['width']
        tree._sync(None, [(param, 'options', 9999)])
        tree.flush()
        self.assertEqual(cam.width, original_width)


class TestQCameraTreeStartStop(unittest.TestCase):

    def test_start_returns_self(self):
        tree = make_tree()
        result = tree.start()
        self.assertIs(result, tree)
        tree.stop()

    def test_stop_when_not_running_is_safe(self):
        tree = make_tree()
        tree.stop()  # source never started — should not raise

    def test_stop_joins_running_source(self):
        tree = make_tree()
        tree.start()
        tree.stop()
        self.assertFalse(tree.source.isRunning())


class TestQCameraTreeUpdateStepUnit(unittest.TestCase):
    '''Direct unit tests for the static _updateStep helper.'''

    def test_skips_a_value_that_is_not_a_finite_number(self):
        for value in (float('nan'), float('inf'), -float('inf')):
            with self.subTest(value=value):
                param = MagicMock()
                param.opts = {'type': 'float'}
                param.value.return_value = value
                QCameraTree._updateStep(param)
                param.setOpts.assert_not_called()

    def test_skips_non_float_type(self):
        param = MagicMock()
        param.opts = {'type': 'int'}
        QCameraTree._updateStep(param)
        param.setOpts.assert_not_called()

    def test_skips_zero_value(self):
        param = MagicMock()
        param.opts = {'type': 'float'}
        param.value.return_value = 0.0
        QCameraTree._updateStep(param)
        param.setOpts.assert_not_called()

    def test_skips_non_numeric_value(self):
        param = MagicMock()
        param.opts = {'type': 'float'}
        param.value.return_value = 'not-a-number'
        QCameraTree._updateStep(param)
        param.setOpts.assert_not_called()

    def test_step_is_tenth_of_order_of_magnitude(self):
        param = MagicMock()
        param.opts = {'type': 'float'}
        param.value.return_value = 250.0
        QCameraTree._updateStep(param)
        param.setOpts.assert_called_once_with(step=10.0)

    def test_step_scales_for_small_values(self):
        param = MagicMock()
        param.opts = {'type': 'float'}
        param.value.return_value = 0.0005
        QCameraTree._updateStep(param)
        param.setOpts.assert_called_once_with(step=1e-5)

    def test_step_uses_magnitude_for_negative_values(self):
        param = MagicMock()
        param.opts = {'type': 'float'}
        param.value.return_value = -250.0
        QCameraTree._updateStep(param)
        param.setOpts.assert_called_once_with(step=10.0)


class TestQCameraTreeAdaptiveStepIntegration(unittest.TestCase):
    '''End-to-end coverage of adaptive stepping through a real tree.

    Uses QNoiseCamera.fps, a genuine registered float property, so the
    _sync/camera.set round trip exercises the real code path rather
    than a property name unknown to the camera.
    '''

    def test_initial_step_set_on_tree_creation(self):
        tree = make_tree()
        step = tree._parameters['fps'].opts['step']
        self.assertAlmostEqual(step, 1.0)  # fps defaults to 30.0

    def test_step_rescales_when_tree_value_edited(self):
        tree = make_tree()
        tree._parameters['fps'].setValue(0.001)
        step = tree._parameters['fps'].opts['step']
        self.assertAlmostEqual(step, 1e-4)

    def test_step_rescales_via_tree_set(self):
        tree = make_tree()
        tree.set('fps', 5000.0)
        step = tree._parameters['fps'].opts['step']
        self.assertAlmostEqual(step, 100.0)


class TestQCameraTreeFollowsTheCamera(unittest.TestCase):

    '''The tree shows what the camera changes on its own.'''

    def make(self, camera=None):
        camera = camera or make_camera()
        tree = QCameraTree(make_source(camera))
        self.addCleanup(tree.stop)
        return tree, camera

    def test_it_asks_the_camera_to_report_what_it_shows(self):
        tree, camera = self.make()
        self.assertEqual(camera._watched, frozenset(tree._parameters))

    def test_it_shows_what_the_camera_did_by_itself(self):
        tree, camera = self.make()
        camera.propertiesChanged.emit({'height': 100})
        self.assertEqual(tree.get('height'), 100)

    def test_it_does_not_send_what_it_is_told_back_to_the_camera(self):
        tree, camera = self.make()
        with patch.object(camera, 'set') as send:
            camera.propertiesChanged.emit({'height': 100})
        send.assert_not_called()

    def test_it_changes_only_what_differs(self):
        tree, camera = self.make()
        height = tree.get('height')
        with patch.object(tree, 'set') as show:
            camera.propertiesChanged.emit({'height': height, 'width': 321})
        show.assert_called_once_with('width', 321)

    def test_a_property_that_it_does_not_show_is_ignored(self):
        tree, camera = self.make()
        with patch.object(tree, 'set') as show:
            camera.propertiesChanged.emit({'nothing': 1})
        show.assert_not_called()

    def test_it_shows_which_controls_can_be_written(self):
        tree, camera = self.make()
        with patch.object(tree, '_showAccess') as show:
            camera.propertiesChanged.emit({'height': 100})
        show.assert_called_once()

    def test_a_setting_that_resets_itself_can_be_chosen_again(self):
        # ExposureAuto = Once turns itself off when the camera has settled;
        # the tree used to go on showing Once, and choosing it again changed
        # nothing, so no command reached the camera.
        state = {'value': 'Off'}
        camera = make_camera()
        camera.registerProperty(
            'Auto', getter=lambda: state['value'],
            setter=lambda value: state.update(value=value), ptype=str,
            limits=['Off', 'Once'])
        tree, _ = self.make(camera)
        tree._parameters['Auto'].setValue('Once')
        tree.flush()
        self.assertEqual(state['value'], 'Once')
        state['value'] = 'Off'                  # the camera has settled
        camera.propertiesChanged.emit({'Auto': 'Off'})
        self.assertEqual(tree.get('Auto'), 'Off')
        tree._parameters['Auto'].setValue('Once')
        tree.flush()
        self.assertEqual(state['value'], 'Once')

    def test_an_edit_reads_the_camera_in_one_request(self):
        tree, camera = self.make()
        with patch.object(camera, 'snapshot',
                          wraps=camera.snapshot) as snapshot:
            tree._parameters['width'].setValue(320)
            tree.flush()
        snapshot.assert_called_once()

    def test_floats_that_agree_are_not_a_difference(self):
        self.assertFalse(QCameraTree._differs(1., 1. + 1e-12))
        self.assertTrue(QCameraTree._differs(1., 1.1))
        self.assertTrue(QCameraTree._differs('Once', 'Off'))
        self.assertFalse(QCameraTree._differs(3, 3))


class SlowCamera(QNoiseCamera):

    '''A camera whose setter waits for a gate, as a camera does that its
    capture thread holds while it waits for a frame.'''

    def __init__(self):
        super().__init__()
        self.gate = threading.Event()
        self.gate.set()                     # open: close it to hold writes
        self.entered = threading.Event()
        self.writes: list = []
        self.threads: set = set()
        self.refuse = None

    def set(self, key, value):
        self.entered.set()
        self.gate.wait(5)
        if self.refuse is not None and self.refuse(key, value):
            raise ValueError(f'{key} = {value!r} is out of range')
        self.writes.append((key, value))
        self.threads.add(threading.current_thread())
        return super().set(key, value)


class TestQCameraTreeThreaded(unittest.TestCase):

    '''The camera is written in a thread of its own.'''

    def setUp(self):
        self.camera = SlowCamera()
        self.tree = QCameraTree(make_source(self.camera))
        self.addCleanup(self.finish)

    def finish(self):
        self.camera.gate.set()
        self.tree.stop()

    def width(self, value):
        self.tree._parameters['width'].setValue(value)

    def test_a_change_does_not_wait_for_the_camera(self):
        self.camera.gate.clear()
        start = time.perf_counter()
        self.width(320)
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 0.5)               # the camera waits 5 s
        self.assertEqual(self.tree.get('width'), 320)   # the tree took it
        self.assertEqual(self.camera.writes, [])
        self.camera.gate.set()
        self.assertTrue(self.tree.flush())
        self.assertEqual(self.camera.width, 320)

    def test_the_camera_is_written_in_another_thread(self):
        self.width(320)
        self.tree.flush()
        self.assertNotIn(threading.current_thread(), self.camera.threads)
        self.assertTrue(self.camera.threads)

    def test_the_latest_value_is_the_one_that_is_written(self):
        self.camera.gate.clear()
        self.width(1)
        self.camera.entered.wait(5)                 # the first is in hand
        for n in range(2, 40):
            self.width(n)                           # a slider is dragged
        self.camera.gate.set()
        self.tree.flush()
        self.assertEqual(self.camera.writes, [('width', 1), ('width', 39)])
        self.assertEqual(self.camera.width, 39)
        self.assertEqual(self.tree.get('width'), 39)

    def test_the_writes_keep_the_order_of_the_last_touch(self):
        self.camera.gate.clear()
        self.width(1)
        self.camera.entered.wait(5)
        self.tree._parameters['height'].setValue(2)
        self.width(3)                               # width again: after height
        self.camera.gate.set()
        self.tree.flush()
        self.assertEqual(self.camera.writes,
                         [('width', 1), ('height', 2), ('width', 3)])

    def test_an_answer_does_not_overwrite_a_newer_edit(self):
        shown = []
        self.tree._parameters['width'].sigValueChanged.connect(
            lambda param, value: shown.append(value))
        self.camera.gate.clear()
        self.width(320)
        self.camera.entered.wait(5)                 # 320 is being written
        self.width(400)                             # the user moves on
        self.camera.gate.set()
        self.tree.flush()
        self.assertEqual(self.tree.get('width'), 400)
        self.assertEqual(self.camera.width, 400)
        # the answer to 320 arrived after 400 was chosen: it was not shown
        self.assertNotIn(320, shown[shown.index(400):])

    def test_an_answer_about_a_newer_edit_is_not_announced(self):
        heard = []
        self.camera.propertiesChanged.connect(
            lambda values: heard.append(dict(values)),
            QtCore.Qt.ConnectionType.DirectConnection)
        self.camera.gate.clear()
        self.width(320)
        self.camera.entered.wait(5)
        self.width(400)
        self.camera.gate.set()
        self.tree.flush()
        self.assertTrue(heard)
        self.assertTrue(all(values.get('width') != 320 for values in heard))
        self.assertEqual(heard[-1]['width'], 400)

    def test_a_change_that_the_camera_reports_does_not_override_an_edit(self):
        self.camera.gate.clear()
        self.width(320)                             # not yet written
        self.tree._showChanges({'width': 111})      # the camera says 111
        self.assertEqual(self.tree.get('width'), 320)
        self.camera.gate.set()
        self.tree.flush()
        self.tree._showChanges({'width': 111})      # now it may
        self.assertEqual(self.tree.get('width'), 111)

    def test_a_camera_that_refuses_is_logged_and_the_tree_shows_the_truth(self):
        before = self.tree.get('width')
        self.camera.refuse = lambda key, value: value > 1000
        with self.assertLogs('QVideo.lib.QCameraTree', 'ERROR') as logs:
            self.width(5000)
            self.tree.flush()
        self.assertIn('width', logs.output[0])
        self.assertEqual(self.tree.get('width'), before)    # shown as it is
        self.camera.refuse = None
        self.width(320)                             # and it goes on
        self.tree.flush()
        self.assertEqual(self.camera.width, 320)

    def test_a_camera_that_cannot_be_read_back_is_logged(self):
        with patch.object(self.tree, '_readback',
                          side_effect=RuntimeError('no frame')):
            with self.assertLogs('QVideo.lib.QCameraTree', 'ERROR') as logs:
                self.width(320)
                self.tree.flush()
        self.assertIn('could not be read back', logs.output[0])
        self.assertEqual(self.camera.width, 320)        # it was written
        self.assertEqual(self.tree.get('width'), 320)   # and the tree kept it

    def test_an_answer_for_a_tree_that_is_gone_is_dropped(self):
        broken = MagicMock()
        broken.emit.side_effect = RuntimeError('wrapped C/C++ object deleted')
        with patch.object(type(self.tree), '_written', broken):
            self.tree._work({'width': (320, 1)})        # does not raise
        self.assertEqual(self.camera.width, 320)

    def test_flush_says_when_the_time_runs_out(self):
        self.camera.gate.clear()
        self.width(320)
        self.assertFalse(self.tree.flush(timeout=0.05))
        self.camera.gate.set()
        self.assertTrue(self.tree.flush())

    def test_flush_with_nothing_to_write_returns_at_once(self):
        start = time.perf_counter()
        self.assertTrue(self.tree.flush())
        self.assertLess(time.perf_counter() - start, 0.5)

    def test_stop_drops_what_waits_and_finishes_what_is_written(self):
        self.camera.gate.clear()
        self.width(1)
        self.camera.entered.wait(5)
        self.tree._parameters['height'].setValue(2)     # waits behind
        stopper = threading.Thread(target=self.tree.stop)
        stopper.start()
        time.sleep(0.05)
        self.camera.gate.set()
        stopper.join(5)
        self.assertFalse(stopper.is_alive())
        self.assertEqual(self.camera.writes, [('width', 1)])
        self.width(7)                                   # nothing is written
        self.assertTrue(self.tree.flush())
        self.assertEqual(self.camera.writes, [('width', 1)])


class RangedCamera(SlowCamera):

    '''A camera with numbers that have ranges, and some that do not.'''

    def __init__(self):
        super().__init__()
        self.state = dict(exposure=0.01, gain=3., offset=640, free=1.5,
                          temperature=31.5, degenerate=2.)
        register = self.registerProperty

        def number(name, ptype, setter=True, **meta):
            register(name, getter=lambda: self.state[name],
                     setter=((lambda value: self.state.update({name: value}))
                             if setter else None),
                     ptype=ptype, **meta)

        number('exposure', float, minimum=1e-5, maximum=30.)
        number('gain', float, minimum=0., maximum=24.)
        number('offset', int, minimum=0, maximum=1920, step=16)
        number('free', float)                             # no range
        number('temperature', float, setter=False,
               minimum=0., maximum=100.)                  # read only
        number('degenerate', float, minimum=2., maximum=2.)


class TestQCameraTreeSliders(unittest.TestCase):

    '''A number that has a range is a slider with a spin box.'''

    def setUp(self):
        self.camera = RangedCamera()
        self.tree = QCameraTree(make_source(self.camera))
        self.addCleanup(self.finish)

    def finish(self):
        self.camera.gate.set()
        self.tree.stop()

    def param(self, name):
        return self.tree._parameters[name]

    def control(self, name):
        return next(iter(self.param(name).items)).widget

    def test_a_number_with_a_range_is_a_slider(self):
        for name in ('exposure', 'gain', 'offset'):
            with self.subTest(name=name):
                self.assertEqual(self.param(name).opts['type'], 'sliderspin')

    def test_the_limits_are_the_range_of_the_camera(self):
        self.assertEqual(self.param('exposure').opts['limits'], (1e-5, 30.))
        self.assertEqual(self.param('gain').opts['limits'], (0., 24.))

    def test_whole_numbers_are_whole_and_keep_their_step(self):
        self.assertTrue(self.param('offset').opts['int'])
        self.assertEqual(self.param('offset').opts['step'], 16)
        self.assertFalse(self.param('gain').opts['int'])

    def test_a_number_without_a_range_is_a_spin_box_as_before(self):
        self.assertEqual(self.param('free').opts['type'], 'float')

    def test_a_number_that_cannot_be_written_is_a_locked_slider(self):
        # a camera unlocks some of its numbers as its settings change, and a
        # control that is not there cannot be unlocked
        self.assertEqual(self.param('temperature').opts['type'], 'sliderspin')
        self.assertFalse(self.param('temperature').opts['enabled'])
        widget = self.control('temperature')
        self.assertFalse(widget.slider.isEnabled())
        self.assertFalse(widget.spin.isEnabled())

    def test_a_range_of_one_point_is_a_spin_box_as_before(self):
        self.assertEqual(self.param('degenerate').opts['type'], 'float')

    def test_other_types_are_as_before(self):
        self.assertEqual(self.param('color').opts['type'], 'bool')

    def test_the_slider_shows_the_value_of_the_camera(self):
        self.assertEqual(self.control('gain').value(), 3.)
        self.assertEqual(self.control('gain').slider.value(),
                         round(1000 * 3 / 24))
        self.assertTrue(self.control('exposure').isLogarithmic())

    def test_dragging_a_slider_writes_the_camera_with_the_latest_value(self):
        self.camera.gate.clear()
        slider = self.control('gain').slider
        slider.setValue(100)
        self.camera.entered.wait(5)                 # the first is in hand
        for position in range(101, 700, 25):
            slider.setValue(position)               # the drag goes on
        self.camera.gate.set()
        self.assertTrue(self.tree.flush())
        gains = [value for key, value in self.camera.writes if key == 'gain']
        self.assertEqual(len(gains), 2)             # not one for each step
        self.assertAlmostEqual(gains[-1], 24 * 676 / 1000)
        self.assertAlmostEqual(self.camera.state['gain'], gains[-1])
        self.assertAlmostEqual(self.control('gain').value(), gains[-1])

    def test_a_change_that_the_camera_reports_moves_the_slider_not_the_camera(
            self):
        self.camera.propertiesChanged.emit({'gain': 6.})
        self.assertEqual(self.tree.get('gain'), 6.)
        self.assertEqual(self.control('gain').slider.value(), 250)
        self.tree.flush()
        self.assertEqual(self.camera.writes, [])            # nothing sent back

    def test_the_spin_box_writes_the_camera_too(self):
        self.control('gain').spin.setValue(18.)
        self.tree.flush()
        self.assertEqual(self.camera.state['gain'], 18.)
        self.assertEqual(self.control('gain').slider.value(), 750)

    def test_the_step_of_a_spin_box_follows_the_value(self):
        self.tree.set('exposure', 5.)
        self.assertAlmostEqual(self.param('exposure').opts['step'], 0.1)
        self.tree.set('exposure', 0.002)
        self.assertAlmostEqual(self.param('exposure').opts['step'], 1e-4)

    def test_the_step_of_whole_numbers_is_left_alone(self):
        self.tree.set('offset', 800)
        self.assertEqual(self.param('offset').opts['step'], 16)


class TestQCameraTreeNotThreaded(unittest.TestCase):

    '''``threaded=False`` writes in the interface thread, inside the change.'''

    def test_the_change_has_taken_effect_when_it_returns(self):
        camera = SlowCamera()
        tree = QCameraTree(make_source(camera), threaded=False)
        self.addCleanup(tree.stop)
        tree._parameters['width'].setValue(320)
        self.assertEqual(camera.width, 320)
        self.assertEqual(camera.threads, {threading.current_thread()})

    def test_flush_has_nothing_to_wait_for(self):
        tree = QCameraTree(make_source(), threaded=False)
        self.addCleanup(tree.stop)
        self.assertTrue(tree.flush())

    def test_the_answer_is_shown_at_once(self):
        camera = SlowCamera()
        tree = QCameraTree(make_source(camera), threaded=False)
        self.addCleanup(tree.stop)
        camera._height = 100                        # the camera did this
        tree._parameters['width'].setValue(320)
        self.assertEqual(tree.get('height'), 100)


if __name__ == '__main__':
    unittest.main()
