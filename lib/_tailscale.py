'''A certificate for this machine from Tailscale.

``tailscale cert`` asks Let's Encrypt, through Tailscale, for a certificate
for the name that the tailnet gives this machine (``scope1.tailnet.ts.net``).
Every browser trusts it, and a device that runs Tailscale reaches the
machine by that name.  This module runs the two commands and returns the
files and the name for :class:`~QVideo.lib.QWebScreen.QWebScreen`.  It needs
Tailscale installed and signed in, and *HTTPS Certificates* turned on for the
tailnet (in the admin console, under DNS).
'''
from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

__all__ = ['TailscaleError', 'certificate']

#: Where the macOS application keeps its command line tool.
_MACOS = '/Applications/Tailscale.app/Contents/MacOS/Tailscale'

_TIMEOUT = 60.


class TailscaleError(RuntimeError):

    '''Tailscale is not there, or cannot give a certificate.'''


def executable() -> str:
    '''Return the path of the ``tailscale`` command.'''
    found = shutil.which('tailscale')
    if found is None and Path(_MACOS).exists():
        found = _MACOS
    if found is None:
        raise TailscaleError(
            'tailscale was not found: install Tailscale and sign in '
            '(https://tailscale.com/download)')
    return found


def _run(*args: str) -> str:
    try:
        done = subprocess.run(args, capture_output=True, text=True,
                              timeout=_TIMEOUT, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise TailscaleError(f'{args[0]} did not run: {error}') from error
    if done.returncode != 0:
        why = (done.stderr or done.stdout).strip()
        raise TailscaleError(f'tailscale {args[1]} failed: {why}')
    return done.stdout


def name(command: str) -> str:
    '''Return the name for which this tailnet gives a certificate.'''
    try:
        status = json.loads(_run(command, 'status', '--json'))
    except json.JSONDecodeError as error:
        raise TailscaleError('tailscale status gave no JSON') from error
    domains = status.get('CertDomains') or []
    if not domains:
        raise TailscaleError(
            'this tailnet has no certificate names: sign in to Tailscale, '
            'and turn on HTTPS Certificates in the admin console '
            '(DNS page)')
    return str(domains[0])


def certificate(directory: str | Path | None = None,
                command: str | None = None) -> tuple[str, str, str]:
    '''Get (or renew) the certificate and return ``(certfile, keyfile,
    name)``.

    Parameters
    ----------
    directory : path, optional
        Where the files go; only the user can read it.  Default
        ``~/.cache/QVideo/tailscale``.
    command : str, optional
        The ``tailscale`` command.  Default: found on the path.

    Raises
    ------
    TailscaleError
        Tailscale is not installed, not signed in, or HTTPS certificates
        are off for the tailnet.
    '''
    command = command or executable()
    where = Path(directory) if directory else (
        Path.home() / '.cache' / 'QVideo' / 'tailscale')
    where.mkdir(parents=True, exist_ok=True, mode=0o700)
    host = name(command)
    certfile = where / f'{host}.crt'
    keyfile = where / f'{host}.key'
    _run(command, 'cert', '--cert-file', str(certfile),
         '--key-file', str(keyfile), host)
    logger.info(f'certificate for {host}')
    return str(certfile), str(keyfile), host
