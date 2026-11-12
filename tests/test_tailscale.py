'''Unit tests for the certificate that Tailscale gives (no Tailscale).'''
import json
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from QVideo.lib import _tailscale
from QVideo.lib.QWebScreen import QWebScreen


def completed(args, stdout='', stderr='', code=0):
    return subprocess.CompletedProcess(args, code, stdout, stderr)


class Fake:

    '''Stands in for ``subprocess.run``: it answers like tailscale.'''

    def __init__(self, domains=('scope1.tail.ts.net',), fail=None):
        self.domains = list(domains)
        self.fail = fail
        self.calls = []

    def __call__(self, args, **kwargs):
        self.calls.append(list(args))
        if args[1] == 'status':
            return completed(args, json.dumps(
                {'CertDomains': self.domains}))
        if args[1] == self.fail:
            return completed(args, stderr='not allowed', code=1)
        files = [args[i + 1] for i, a in enumerate(args)
                 if a in ('--cert-file', '--key-file')]
        for name in files:
            with open(name, 'w') as file:
                file.write('x')
        return completed(args)


class TestCertificate(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def get(self, fake):
        with patch.object(_tailscale.subprocess, 'run', fake):
            return _tailscale.certificate(self.directory.name, 'tailscale')

    def test_it_returns_the_files_and_the_name(self):
        fake = Fake()
        certfile, keyfile, name = self.get(fake)
        self.assertEqual(name, 'scope1.tail.ts.net')
        self.assertEqual(os.path.dirname(certfile), self.directory.name)
        self.assertTrue(os.path.exists(certfile))
        self.assertTrue(os.path.exists(keyfile))
        cert = fake.calls[-1]
        self.assertEqual(cert[:2], ['tailscale', 'cert'])
        self.assertEqual(cert[-1], 'scope1.tail.ts.net')

    def test_a_tailnet_without_certificate_names_says_what_to_turn_on(self):
        with self.assertRaisesRegex(_tailscale.TailscaleError,
                                    'HTTPS Certificates'):
            self.get(Fake(domains=[]))

    def test_a_refusal_is_an_error_that_says_why(self):
        with self.assertRaisesRegex(_tailscale.TailscaleError,
                                    'not allowed'):
            self.get(Fake(fail='cert'))

    def test_the_command_that_is_missing_says_where_to_get_it(self):
        with (patch.object(_tailscale.shutil, 'which', return_value=None),
              patch.object(_tailscale.Path, 'exists', return_value=False),
              self.assertRaisesRegex(_tailscale.TailscaleError,
                                     'install Tailscale')):
            _tailscale.executable()

    def test_a_screen_from_tailscale_serves_https_at_the_name(self):
        fake = Fake()
        with (patch.object(_tailscale.subprocess, 'run', fake),
              patch.object(_tailscale, 'executable',
                           return_value='tailscale')):
            web = QWebScreen.fromTailscale(directory=self.directory.name,
                                           port=443)
            self.assertEqual(web.hostname, 'scope1.tail.ts.net')
            self.assertTrue(web.secure)
            self.assertEqual(web.url, 'https://scope1.tail.ts.net/')
            before = len(fake.calls)
            web._renew()                        # what the server asks hourly
            self.assertGreater(len(fake.calls), before)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
