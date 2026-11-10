'''Unit tests for the controls of QWebScreen: what a page may change.'''
import asyncio
import json
import time
import unittest

from qtpy import QtCore, QtWidgets

from QVideo.cameras.Noise import QNoiseCamera
from QVideo.lib import _webcontrols
from QVideo.lib.QCamera import PropertySpec
from QVideo.lib.QWebScreen import QWebScreen
from QVideo.tests.signals import record

try:
    import aiohttp
except ImportError:                     # pragma: no cover
    aiohttp = None


app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def spec(ptype=float, setter=lambda value: None, **meta):
    return PropertySpec(lambda: None, setter, ptype, **meta)


class TestCoerce(unittest.TestCase):

    def test_a_number_is_clipped_to_its_limits(self):
        limits = spec(float, minimum=1., maximum=10.)
        self.assertEqual(_webcontrols.coerce(limits, 50), 10.)
        self.assertEqual(_webcontrols.coerce(limits, -3.5), 1.)
        self.assertEqual(_webcontrols.coerce(limits, 2), 2.)
        self.assertIsInstance(_webcontrols.coerce(limits, 2), float)

    def test_an_integer_is_rounded(self):
        count = spec(int, minimum=0, maximum=255)
        self.assertEqual(_webcontrols.coerce(count, 12.6), 13)
        self.assertEqual(_webcontrols.coerce(count, 999), 255)

    def test_what_is_not_a_number_is_refused(self):
        count = spec(int)
        for bad in ('5', None, float('nan'), float('inf'), True, [1]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                _webcontrols.coerce(count, bad)

    def test_a_boolean_must_be_one(self):
        flag = spec(bool)
        self.assertIs(_webcontrols.coerce(flag, True), True)
        for bad in (1, 'true', None):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                _webcontrols.coerce(flag, bad)

    def test_a_choice_must_be_listed(self):
        mode = spec(str, limits=['Off', 'Once'])
        self.assertEqual(_webcontrols.coerce(mode, 'Once'), 'Once')
        with self.assertRaises(ValueError):
            _webcontrols.coerce(mode, 'Always')

    def test_a_string_without_choices_cannot_be_set(self):
        with self.assertRaises(ValueError):
            _webcontrols.coerce(spec(str), 'x')


class TestChoose(unittest.TestCase):

    def setUp(self):
        self.properties = {
            'Gain': spec(float), 'width': spec(int), 'fps': spec(float),
            'color': spec(bool, setter=None), 'note': spec(str),
            'exposure': spec(float, setter=None)}

    def test_the_default_is_the_usual_writable_ones(self):
        self.assertEqual(_webcontrols.choose(self.properties),
                         ['Gain', 'fps'])

    def test_a_hidden_property_is_not_offered_by_default(self):
        self.properties['fps'].hidden = True
        self.assertEqual(_webcontrols.choose(self.properties), ['Gain'])
        # but an application that names it gets it
        self.assertEqual(_webcontrols.choose(self.properties, ['fps']),
                         ['fps'])

    def test_named_properties_are_kept_if_a_page_can_show_them(self):
        self.assertEqual(
            _webcontrols.choose(self.properties,
                                ['width', 'nothing', 'note', 'color']),
            ['width', 'color'])

    def test_an_empty_list_exposes_nothing(self):
        self.assertEqual(_webcontrols.choose(self.properties, []), [])

    def test_describe_gives_what_a_page_needs(self):
        properties = {'gain': spec(float, minimum=0., maximum=1., step=.1),
                      'mode': spec(str, limits=['a', 'b']),
                      'off': spec(bool, setter=None)}
        entries = _webcontrols.describe(
            properties, ['gain', 'mode', 'off'],
            {'gain': .5, 'mode': 'a', 'off': False})
        self.assertEqual(entries[0], dict(
            name='gain', label='Gain', type='float', value=.5,
            writable=True, min=0., max=1., step=.1))
        self.assertEqual(entries[1]['limits'], ['a', 'b'])
        self.assertFalse(entries[2]['writable'])
        json.dumps(entries)

    def test_a_label_is_a_name_for_a_person(self):
        for name, label in (('ExposureTime', 'Exposure time'),
                            ('exposuretime', 'Exposure time'),
                            ('BlackLevel', 'Black level'),
                            ('AcquisitionFrameRate', 'Frame rate'),
                            ('mirrored', 'Mirror'), ('Gain', 'Gain'),
                            ('TriggerMode', 'Trigger mode'),
                            ('gamma', 'Gamma')):
            self.assertEqual(_webcontrols.label(name), label)

    def test_a_unit_is_sent_only_when_the_camera_says_one(self):
        properties = {'exposure': spec(float, unit='us'),
                      'gain': spec(float),
                      'odd': spec(float, unit=3)}
        entries = _webcontrols.describe(
            properties, ['exposure', 'gain', 'odd'],
            {'exposure': 1., 'gain': 1., 'odd': 1.})
        self.assertEqual(entries[0]['unit'], 'us')
        self.assertNotIn('unit', entries[1])
        self.assertNotIn('unit', entries[2])

    def test_a_property_without_a_value_is_left_out(self):
        entries = _webcontrols.describe({'gain': spec()}, ['gain'], {})
        self.assertEqual(entries, [])


@unittest.skipIf(aiohttp is None, 'aiohttp not installed')
class TestControl(unittest.TestCase):

    '''A page asks, the operator answers, and then the page can set.'''

    def setUp(self):
        self.camera = QNoiseCamera()
        self.addCleanup(self.camera.close)
        self.web = QWebScreen(host='127.0.0.1', port=0, camera=self.camera,
                              controlOverHttp=True)
        self.web.start()
        self.addCleanup(self.web.stop)
        self.base = f'http://127.0.0.1:{self.web.port}'

    def tearDown(self):
        app.processEvents()

    @staticmethod
    def client():
        return aiohttp.ClientSession(
            cookie_jar=aiohttp.CookieJar(unsafe=True))

    async def join(self, session):
        self.web.openPairing()
        code = self.web.pairingUrl.rsplit('/', 1)[1]
        async with session.get(f'{self.base}/join/{code}',
                               allow_redirects=False):
            pass
        return self.web.viewers[-1]['id']

    @staticmethod
    async def note(ws, kind, timeout=3., **match):
        '''Return the next text message of the given type.'''
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            app.processEvents()
            try:
                message = await ws.receive(timeout=0.05)
            except asyncio.TimeoutError:
                continue
            if message.type != aiohttp.WSMsgType.TEXT:
                continue
            note = json.loads(message.data)
            if note['type'] == kind and all(
                    note.get(key) == value for key, value in match.items()):
                return note
        raise AssertionError(f'no {kind} {match} in {timeout} s')

    def ask(self, work):
        '''Pair a browser, open its page, and run ``work(session, ws, id)``.'''
        async def run():
            async with self.client() as session:
                ident = await self.join(session)
                async with session.ws_connect(self.base + '/ws') as ws:
                    return await work(session, ws, ident)
        return asyncio.run(run())

    @staticmethod
    async def send(ws, **message):
        await ws.send_str(json.dumps(message))

    def test_the_page_is_told_what_it_can_change(self):
        async def work(session, ws, ident):
            return await self.note(ws, 'hello')
        hello = self.ask(work)
        names = [entry['name'] for entry in hello['controls']]
        self.assertEqual(names, ['fps', 'blacklevel', 'whitelevel'])
        self.assertTrue(hello['available'])
        self.assertEqual(hello['state'], 'none')
        black = hello['controls'][1]
        self.assertEqual((black['type'], black['value']), ('int', 48))

    def test_control_needs_https_unless_the_program_says_otherwise(self):
        self.web.controlOverHttp = False
        self.assertFalse(self.web.controlAvailable)
        self.assertIn('https', self.web.controlReason)

        async def work(session, ws, ident):
            hello = await self.note(ws, 'hello')
            await self.send(ws, type='request')
            note = await self.note(ws, 'control')
            return hello, note
        hello, note = self.ask(work)
        self.assertFalse(hello['available'])
        self.assertEqual(note['state'], 'none')     # no prompt is raised
        self.assertEqual(self.web.viewers[0]['control'], 'none')

    def test_without_pairing_nothing_can_be_controlled(self):
        other = QWebScreen(camera=self.camera, access=False,
                           controlOverHttp=True)
        self.assertFalse(other.controlAvailable)

    def test_without_a_camera_or_properties_there_is_nothing_to_control(self):
        self.assertFalse(QWebScreen(controlOverHttp=True).controlAvailable)
        other = QWebScreen(camera=self.camera, properties=[],
                           controlOverHttp=True)
        self.assertFalse(other.controlAvailable)

    def test_a_request_raises_a_prompt_and_a_grant_allows_a_set(self):
        asked = record(self.web.controlRequested)
        changed = record(self.camera.propertiesChanged)

        async def work(session, ws, ident):
            await self.note(ws, 'hello')
            await self.send(ws, type='request')
            await self.note(ws, 'control', state='requested')
            app.processEvents()
            self.assertEqual(asked, [(ident,)])
            self.assertEqual(self.web.viewers[0]['control'], 'requested')
            self.assertTrue(self.web.grantControl(ident))
            await self.note(ws, 'control', state='granted')
            await self.send(ws, type='set', name='blacklevel', value=40)
            values = await self.note(ws, 'values')
            self.assertEqual(self.web.controller, ident)
            return values
        values = self.ask(work)
        self.assertEqual(self.camera.get('blacklevel'), 40)
        self.assertEqual(values['values']['blacklevel'], 40)
        self.assertTrue(changed)            # the Qt tree follows

    def test_a_set_tells_the_tree_about_what_it_watches_too(self):
        '''A tree shows more than the page does (a new resolution changes the
        width it shows): what it watches is announced with what the page
        shows.'''
        self.web.properties = ['blacklevel']
        self.camera.watch(['whitelevel'])
        heard = record(self.camera.propertiesChanged)
        self.web._apply(self.camera, 'blacklevel', 40)
        self.assertEqual(sorted(heard[0][0]), ['blacklevel', 'whitelevel'])

    def test_a_set_without_control_does_nothing(self):
        before = self.camera.get('blacklevel')

        async def work(session, ws, ident):
            await self.note(ws, 'hello')
            await self.send(ws, type='set', name='blacklevel', value=40)
            await self.send(ws, type='request')     # after: orders the two
            await self.note(ws, 'control', state='requested')
        self.ask(work)
        self.assertEqual(self.camera.get('blacklevel'), before)

    def test_a_refusal_is_told_and_the_page_must_wait_to_ask_again(self):
        asked = record(self.web.controlRequested)

        async def work(session, ws, ident):
            await self.note(ws, 'hello')
            await self.send(ws, type='request')
            await self.note(ws, 'control', state='requested')
            self.web.denyControl(ident)
            await self.note(ws, 'control', state='denied')
            await self.send(ws, type='request')
            await self.note(ws, 'control', state='denied')
            app.processEvents()
        self.ask(work)
        self.assertEqual(len(asked), 1)             # no second prompt
        self.assertEqual(self.web.viewers[0]['control'], 'none')

    def test_a_page_can_set_only_what_is_exposed_and_only_valid_values(self):
        before = self.camera.get('blacklevel')

        async def work(session, ws, ident):
            await self.note(ws, 'hello')
            await self.send(ws, type='request')
            await self.note(ws, 'control', state='requested')
            self.web.grantControl(ident)
            await self.note(ws, 'control', state='granted')
            for name, value in (('width', 100), ('nothing', 1),
                                ('blacklevel', 'x'), ('blacklevel', None),
                                ('blacklevel', float('nan')), (7, 1)):
                await self.send(ws, type='set', name=name, value=value)
            await ws.send_str('not json')
            await ws.send_str('[1, 2]')
            await self.send(ws, type='set', name='whitelevel', value=9999)
            await self.note(ws, 'values')
        self.ask(work)
        self.assertEqual(self.camera.get('width'), 640)
        self.assertEqual(self.camera.get('blacklevel'), before)
        self.assertEqual(self.camera.get('whitelevel'), 255)    # clipped

    def test_one_browser_controls_at_a_time(self):
        async def run():
            async with self.client() as one, self.client() as two:
                first = await self.join(one)
                second = await self.join(two)
                async with one.ws_connect(self.base + '/ws') as ws1, \
                        two.ws_connect(self.base + '/ws') as ws2:
                    for ws, ident in ((ws1, first), (ws2, second)):
                        await self.note(ws, 'hello')
                        await self.send(ws, type='request')
                        await self.note(ws, 'control', state='requested')
                        self.web.grantControl(ident)
                        await self.note(ws, 'control', state='granted')
                    await self.note(ws1, 'control', state='revoked')
                    return first, second
        first, second = asyncio.run(run())
        self.assertEqual(self.web.controller, None)     # both pages closed
        self.assertNotEqual(first, second)

    def test_the_operator_can_take_control_back(self):
        before = self.camera.get('blacklevel')

        async def work(session, ws, ident):
            await self.note(ws, 'hello')
            await self.send(ws, type='request')
            await self.note(ws, 'control', state='requested')
            self.web.grantControl(ident)
            await self.note(ws, 'control', state='granted')
            self.web.revokeControl()
            await self.note(ws, 'control', state='revoked')
            await self.send(ws, type='set', name='blacklevel', value=40)
            await self.send(ws, type='request')     # orders the two
            await self.note(ws, 'control', state='requested')
        self.ask(work)
        self.assertEqual(self.camera.get('blacklevel'), before)
        self.assertIsNone(self.web.controller)

    def test_a_page_can_give_control_up(self):
        async def work(session, ws, ident):
            await self.note(ws, 'hello')
            await self.send(ws, type='request')
            await self.note(ws, 'control', state='requested')
            self.web.grantControl(ident)
            await self.note(ws, 'control', state='granted')
            await self.send(ws, type='release')
            await self.note(ws, 'control', state='none')
            self.assertIsNone(self.web.controller)
        self.ask(work)

    def test_control_ends_when_the_page_closes(self):
        async def work(session, ws, ident):
            await self.note(ws, 'hello')
            await self.send(ws, type='request')
            await self.note(ws, 'control', state='requested')
            self.web.grantControl(ident)
            await self.note(ws, 'control', state='granted')
        self.ask(work)
        deadline = time.monotonic() + 3.
        while self.web.controller and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertIsNone(self.web.controller)

    def test_a_change_by_the_camera_reaches_the_pages(self):
        async def work(session, ws, ident):
            await self.note(ws, 'hello')
            self.camera.propertiesChanged.emit({'fps': 12., 'width': 1})
            return await self.note(ws, 'values')
        values = self.ask(work)['values']
        self.assertEqual(values, {'fps': 12.})     # only what is exposed

    def test_changes_that_come_fast_reach_a_page_as_one_message(self):
        async def work(session, ws, ident):
            await self.note(ws, 'hello')
            for value in range(1, 21):
                self.camera.propertiesChanged.emit({'fps': float(value)})
            app.processEvents()
            first = await self.note(ws, 'values')
            try:
                second = await self.note(ws, 'values', timeout=0.5)
            except AssertionError:
                second = None
            return first, second
        first, second = self.ask(work)
        self.assertEqual(first['values'], {'fps': 20.})   # the newest
        self.assertIsNone(second)

    def test_a_viewer_that_was_removed_cannot_be_granted_control(self):
        self.assertFalse(self.web.grantControl('nobody'))
        self.web.denyControl('nobody')              # and this is safe
        self.web.revokeControl('nobody')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
