'''Diagnostic script for Spinnaker GenTL producer compliance.

Probes which parts of the GenICam/GenTL standard the Spinnaker_GenTL.cti
producer implements, and identifies why the node map is inaccessible via
the harvesters/genicam stack.

Usage::

    python probe_spinnaker_gentl.py

The Spinnaker SDK must be installed and GENICAM_GENTL64_PATH must be set.
'''

import os
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.WARNING,
                    format='%(levelname)s  %(name)s: %(message)s')

# ── 1. Locate the CTI file ────────────────────────────────────────────────────

def find_cti(name):
    for directory in os.environ.get('GENICAM_GENTL64_PATH', '').split(os.pathsep):
        candidate = Path(directory) / name
        if candidate.exists():
            return str(candidate)
    return None


CTI = find_cti('Spinnaker_GenTL.cti')

def check(label, value=None, *, ok=True):
    status = 'PASS' if ok else 'FAIL'
    if value is not None:
        print(f'  [{status}] {label}: {value}')
    else:
        print(f'  [{status}] {label}')
    return ok


print()
print('=== Spinnaker GenTL compliance probe ===')
print()

print('── 1. CTI discovery ──')
if not check('GENICAM_GENTL64_PATH set',
             os.environ.get('GENICAM_GENTL64_PATH', '(not set)'),
             ok=bool(os.environ.get('GENICAM_GENTL64_PATH'))):
    sys.exit(1)
if not check('Spinnaker_GenTL.cti found', CTI, ok=CTI is not None):
    sys.exit(1)

# ── 2. Harvester init ─────────────────────────────────────────────────────────

print()
print('── 2. Harvester initialisation ──')

from harvesters.core import Harvester

h = Harvester()
try:
    h.add_file(CTI)
    check('add_file')
except Exception as e:
    check('add_file', str(e), ok=False)
    sys.exit(1)

try:
    h.update()
    check('update / enumerate cameras')
except Exception as e:
    check('update', str(e), ok=False)
    sys.exit(1)

check('cameras found', len(h.device_info_list),
      ok=len(h.device_info_list) > 0)
for i, info in enumerate(h.device_info_list):
    print(f'         camera {i}: {info}')

if not h.device_info_list:
    print('  No cameras — cannot continue.')
    h.reset()
    sys.exit(1)

# ── 3. Device creation ────────────────────────────────────────────────────────

print()
print('── 3. Device creation ──')

try:
    dev = h.create(0)
    check('harvester.create(0)')
except Exception as e:
    check('harvester.create(0)', str(e), ok=False)
    h.reset()
    sys.exit(1)

check('remote_device not None', ok=dev.remote_device is not None)
check('device (local) not None', ok=dev.device is not None)

# ── 4. Remote port URL list ───────────────────────────────────────────────────
#
# harvesters._retrieve_file_path() queries port.url_info_list to find the
# device-description XML.  An empty list means no XML → NodeMap never connected.

print()
print('── 4. Remote device port / XML discovery ──')

try:
    remote_port = dev.remote_device.module.remote_port
    check('remote_device.module.remote_port accessible')
except Exception as e:
    check('remote_device.module.remote_port', str(e), ok=False)
    remote_port = None

if remote_port is not None:
    try:
        urls = remote_port.url_info_list
        check('url_info_list accessible', f'{len(urls)} URL(s)', ok=True)
        if urls:
            for u in urls:
                print(f'         {u.url}')
        else:
            check('url_info_list non-empty', '(empty — node map will not load)',
                  ok=False)
    except Exception as e:
        check('url_info_list', str(e), ok=False)

# ── 5. Local device port URL list ─────────────────────────────────────────────

print()
print('── 5. Local device port / XML discovery ──')

try:
    local_port = dev.device.module.port
    check('device.module.port accessible')
except Exception as e:
    check('device.module.port', str(e), ok=False)
    local_port = None

if local_port is not None:
    try:
        urls = local_port.url_info_list
        check('local url_info_list', f'{len(urls)} URL(s)', ok=True)
        for u in urls:
            print(f'         {u.url}')
    except Exception as e:
        check('local url_info_list', str(e), ok=False)

# ── 6. Node map connection attempt ────────────────────────────────────────────

print()
print('── 6. Node map connection ──')

from genicam.genapi import NodeMap
from harvesters.core import ConcretePort

nm = NodeMap()

if remote_port is not None:
    try:
        urls = remote_port.url_info_list
        if urls:
            url = urls[0].url
            location = url.split(':', 1)[0].lower()
            check('URL scheme', location)
            if location == 'local':
                _, rest = url.split(':', 1)
                file_name, address, size = rest.split(';')
                address = int(address, 16)
                size = int(size.split('?')[0], 16)
                nbytes, data = remote_port.read(address, size)
                check('read XML from device port', f'{nbytes} bytes')
                import tempfile, zipfile, io
                tmp = tempfile.NamedTemporaryFile(suffix='.zip', delete=False)
                tmp.write(data)
                tmp.close()
                try:
                    nm.load_xml_from_zip_file(tmp.name)
                    check('load_xml_from_zip_file')
                except Exception:
                    nm.load_xml_from_file(tmp.name)
                    check('load_xml_from_file (fallback)')
                concrete_port = ConcretePort(remote_port)
                nm.connect(concrete_port, remote_port.name)
                check('NodeMap.connect')
                # List top-level nodes in the manually-connected map
                try:
                    top_nodes = [n.node.name for n in nm.nodes
                                 if hasattr(n, 'node')]
                    check('manual nm top-level nodes', len(top_nodes))
                    print(f'         {top_nodes}')
                except Exception as e:
                    check('manual nm top-level nodes', str(e), ok=False)
                for name in ('Root', 'root', 'Device', 'DeviceControl',
                             'ImageFormatControl'):
                    try:
                        found = nm.has_node(name)
                        check(f'manual nm.has_node("{name}")', found, ok=found)
                    except Exception as e:
                        check(f'manual nm.has_node("{name}")', str(e), ok=False)
            else:
                check('URL scheme handled', location, ok=False)
        else:
            check('URL list non-empty (needed for node map)', ok=False)
    except Exception as e:
        check('node map manual load/connect', str(e), ok=False)
else:
    check('remote port available for node map probe', ok=False)

# ── 6b. Replay harvesters _create_node_map path ───────────────────────────────
#
# harvesters calls _retrieve_file_path + _save_file + load_xml_from_zip_file
# during h.create(), before our probe code runs.  Replaying those calls now
# (with the port already settled) shows whether the failure is a content/format
# issue or a timing issue (port not ready at create() time).

print()
print('── 6b. Harvesters internal path replay ──')

import harvesters.core as _hc
from genicam.genapi import GenericException as GenApi_GenericException

if remote_port is not None:
    try:
        clean_up, hv_file_path = _hc.Module._retrieve_file_path(
            port=remote_port)
        check('_retrieve_file_path returned a path',
              repr(hv_file_path), ok=hv_file_path is not None)
    except Exception as e:
        check('_retrieve_file_path', str(e), ok=False)
        hv_file_path = None

    if hv_file_path is not None:
        import pathlib
        check('saved file exists', hv_file_path,
              ok=pathlib.Path(hv_file_path).exists())
        nm2 = NodeMap()
        try:
            nm2.load_xml_from_zip_file(hv_file_path)
            check('load_xml_from_zip_file (harvesters path)')
        except GenApi_GenericException as e:
            check('load_xml_from_zip_file (harvesters path)',
                  str(e), ok=False)
            try:
                nm2.load_xml_from_file(hv_file_path)
                check('load_xml_from_file fallback')
            except GenApi_GenericException as e2:
                check('load_xml_from_file fallback', str(e2), ok=False)
        except Exception as e:
            check('load_xml_from_zip_file (harvesters path)',
                  str(e), ok=False)
else:
    check('remote port available for harvesters path replay', ok=False)

# ── 7. Node map access (harvesters-provided) ──────────────────────────────────

print()
print('── 7. Node map access ──')

try:
    hv_nm = dev.remote_device.node_map
    check('remote_device.node_map property')
    for name in ('Root', 'root', 'Device', 'DeviceControl',
                 'ImageFormatControl'):
        try:
            found = hv_nm.has_node(name)
            check(f'node_map.has_node("{name}")', found, ok=found)
        except Exception as e:
            check(f'node_map.has_node("{name}")', str(e), ok=False)
    # If nothing above passed, try listing nodes directly
    try:
        top_nodes = [n.node.name for n in hv_nm.nodes if hasattr(n, 'node')]
        check('harvesters nm top-level nodes', len(top_nodes))
        print(f'         {top_nodes}')
    except Exception as e:
        check('harvesters nm top-level nodes', str(e), ok=False)
except Exception as e:
    check('remote_device.node_map property', str(e), ok=False)

# ── 8. Data stream GenTL coverage ────────────────────────────────────────────

print()
print('── 8. Data stream GenTL functions ──')

try:
    streams = dev.data_streams
    check('data_streams accessible', f'{len(streams)} stream(s)')
    if streams:
        ds = streams[0]
        for attr in ('buffer_announce_min', 'num_buffers_announced',
                     'num_chunks_max', 'payload_size'):
            try:
                val = getattr(ds.module, attr, '(no attr)')
                check(f'data_stream.{attr}', val)
            except Exception as e:
                check(f'data_stream.{attr}', str(e), ok=False)
except Exception as e:
    check('data_streams', str(e), ok=False)

# ── 9. Teardown ───────────────────────────────────────────────────────────────

print()
print('── 9. Teardown ──')

try:
    dev.destroy()
    check('device.destroy()')
except Exception as e:
    check('device.destroy()', str(e), ok=False)

try:
    h.reset()
    check('harvester.reset()')
except Exception as e:
    check('harvester.reset()', str(e), ok=False)

print()
print('=== probe complete ===')
print()
