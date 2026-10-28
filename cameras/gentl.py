'''GenTL environment helpers and a command-line diagnostic.

This module deliberately imports nothing from ``harvesters`` or
``genicam`` at module level, so that it works when those packages are
missing.  Run it to find out why a GenICam camera cannot be opened::

    python -m QVideo.cameras.gentl Spinnaker_GenTL.cti

Without arguments, it reports every ``.cti`` file found on
``GENICAM_GENTL64_PATH``.
'''
import importlib
import os
import sys
from collections.abc import Callable
from pathlib import Path


__all__ = ['ENV', 'gentlPaths', 'findProducer', 'check', 'main']


ENV = 'GENICAM_GENTL64_PATH'

_INSTALL = 'pip install genicam harvesters'


def gentlPaths() -> list[str]:
    '''Return the non-empty directories listed in ``GENICAM_GENTL64_PATH``.'''
    return [d for d in os.environ.get(ENV, '').split(os.pathsep) if d]


def findProducer(*filenames: str) -> str | None:
    '''Return the first of *filenames* found on ``GENICAM_GENTL64_PATH``.

    Parameters
    ----------
    *filenames : str
        Producer ``.cti`` filenames to search for, in priority order.

    Returns
    -------
    str or None
        Path to the first file found, or ``None``.
    '''
    for directory in gentlPaths():
        for name in filenames:
            candidate = Path(directory) / name
            if candidate.exists():
                return str(candidate)
    return None


def check(*filenames: str) -> list[tuple[bool, str]]:
    '''Check each prerequisite for opening a GenICam camera.

    Parameters
    ----------
    *filenames : str
        Producer ``.cti`` filenames to look for.  If none are given,
        all ``.cti`` files on the path are reported.

    Returns
    -------
    list of (bool, str)
        One ``(passed, message)`` entry per check.  Later checks are
        skipped when the ones they depend on fail.
    '''
    results: list[tuple[bool, str]] = []

    def report(ok: bool, message: str) -> bool:
        results.append((ok, message))
        return ok

    packages = _checkPackages(report)
    directories = _checkPath(report)
    producers = _findProducers(report, directories, filenames)
    if packages and producers:
        _checkProducers(report, producers)
    return results


def _checkPackages(report: Callable[[bool, str], bool]) -> bool:
    '''Report whether the Python packages that GenICam needs import.'''
    packages = True
    for module in ('genicam.genapi', 'harvesters.core'):
        try:
            importlib.import_module(module)
            report(True, f'{module} imports')
        except Exception as ex:
            packages = report(
                False, f'cannot import {module}: {ex}\n'
                f'      Install with: {_INSTALL}\n'
                '      If this is a numpy ABI error: pip install "numpy<2"'
            ) and packages
    return packages


def _checkPath(report: Callable[[bool, str], bool]) -> list[str]:
    '''Report on the producer search path and return its directories.'''
    directories = gentlPaths()
    if not directories:
        report(False, f'{ENV} is not set; point it at the directory '
                      'containing the GenTL producer (.cti file)')
    for directory in directories:
        exists = Path(directory).is_dir()
        report(exists, f'{ENV} entry {directory}'
                       + ('' if exists else ' does not exist'))
    return directories


def _findProducers(report: Callable[[bool, str], bool],
                   directories: list[str],
                   filenames: tuple[str, ...]) -> list[str]:
    '''Report the producers that were asked for, or all on the path.'''
    producers: list[str] = []
    if not filenames:
        for directory in directories:
            found = sorted(Path(directory).glob('*.cti'))
            producers += [str(p) for p in found]
        report(bool(producers),
               f'{len(producers)} GenTL producer(s) found'
               + ''.join(f'\n      {p}' for p in producers))
        return producers
    for name in filenames:
        path = findProducer(name)
        if path is None:
            report(False, f'{name} not found on {ENV}')
        else:
            report(True, f'found {path}')
            producers.append(path)
    return producers


def _checkProducers(report: Callable[[bool, str], bool],
                    producers: list[str]) -> None:
    '''Report whether each producer loads and which cameras it sees.'''
    from harvesters.core import Harvester
    for path in producers:
        h = Harvester()
        try:
            h.add_file(path)
            h.update()
            devices = h.device_info_list
            report(True, f'{Path(path).name} loads; '
                         f'{len(devices)} camera(s) found')
            for n, info in enumerate(devices):
                p = info.property_dict
                report(True, f'  [{n}] {p.get("model")} '
                             f'(SN {p.get("serial_number")})')
            if not devices:
                report(False, 'no cameras detected: check the cable, '
                              'power and USB/network permissions')
        except Exception as ex:
            report(False, f'cannot load {path}: {ex}')
        finally:
            h.reset()


def main(argv: list[str] | None = None) -> int:  # pragma: no cover
    '''Print the results of :func:`check`; return a process exit code.'''
    results = check(*(sys.argv[1:] if argv is None else argv))
    for ok, message in results:
        print(f'[{"ok" if ok else "FAIL"}] {message}')
    return 0 if all(ok for ok, _ in results) else 1


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
