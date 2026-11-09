'''The web page that :class:`~QVideo.lib.QWebScreen.QWebScreen` serves.

One self-contained page: no framework and nothing to install.  It opens a
WebSocket to ``/ws``, draws each frame on a canvas that fits the window, and
reconnects when the server goes away, and stops when the instrument has
unpaired it.  A frame that arrives while the
previous one is being decoded replaces it, so a slow tablet shows the newest
frame and never falls behind.  Tapping the page shows or hides the readout.

When the server describes camera properties (a ``hello`` message) the page
offers a Controls panel: a control for each property, which works once the
operator has allowed it.  The server decides everything; the page only asks.
'''

__all__ = ['PAGE', 'DENIED', 'EXPIRED']

PAGE = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1,
      viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<title>QVideo</title>
<style>
  html, body { margin: 0; height: 100%; background: #000; overflow: hidden; }
  canvas { position: fixed; inset: 0; width: 100vw; height: 100vh;
           object-fit: contain; background: #000; }
  #hud { position: fixed; left: 8px; top: 6px; padding: 2px 6px;
         font: 13px/1.4 -apple-system, system-ui, sans-serif; color: #ddd;
         background: rgba(0, 0, 0, .55); border-radius: 4px;
         pointer-events: none; }
  button, select, input { font: 15px -apple-system, system-ui, sans-serif; }
  #gear { position: fixed; right: 8px; top: 6px; padding: 8px 12px;
          border: 0; border-radius: 6px; color: #ddd;
          background: rgba(0, 0, 0, .55); }
  #panel { position: fixed; right: 8px; top: 48px; width: min(22em, 90vw);
           max-height: calc(100vh - 64px); overflow: auto; padding: 10px;
           box-sizing: border-box; border-radius: 8px; color: #ddd;
           background: rgba(0, 0, 0, .78);
           font: 14px/1.4 -apple-system, system-ui, sans-serif; }
  #panel[hidden], #gear[hidden] { display: none; }
  #status { margin-bottom: 8px; }
  #ask { min-height: 44px; width: 100%; margin-bottom: 10px; border: 0;
         border-radius: 6px; color: #fff; background: #57068c; }
  #ask:disabled { opacity: .5; }
  .row { margin: 10px 0; }
  .row label { display: flex; justify-content: space-between; }
  .row input[type=range], .row select { width: 100%; min-height: 32px; }
  .row input:disabled, .row select:disabled { opacity: .45; }
</style>
</head>
<body>
<canvas id="view" width="16" height="16"></canvas>
<div id="hud">connecting...</div>
<button id="gear" hidden>Controls</button>
<div id="panel" hidden>
  <div id="status"></div>
  <button id="ask"></button>
  <div id="rows"></div>
</div>
<script>
'use strict';
const canvas = document.getElementById('view');
const ctx = canvas.getContext('2d');
const hud = document.getElementById('hud');
let socket = null;
let pending = null;      // the newest message that has not been drawn
let drawing = false;
let shown = 0;           // frames drawn in the last second
let rate = 0;
let head = null;         // header of the frame on the canvas
let state = 'connecting...';

function readout() {
  if (head === null || state !== 'live') {
    hud.textContent = state;
    return;
  }
  hud.textContent = '#' + head.index + '   ' + head.width + ' x ' +
                    head.height + '   ' + rate + ' frames/s';
}

// Retry, unless the server no longer knows this browser (it restarted, or
// the code was changed): then only a new scan helps.
async function retry() {
  try {
    const reply = await fetch('/session', { cache: 'no-store' });
    if (reply.status === 401) {
      state = 'not paired: scan the code on the instrument';
      readout();
      return;
    }
  } catch (error) {
    // the server is not there yet: try again
  }
  connect();
}

function connect() {
  if (socket !== null && socket.readyState <= 1) return;   // already open
  const scheme = location.protocol === 'https:' ? 'wss://' : 'ws://';
  socket = new WebSocket(scheme + location.host + '/ws');
  socket.binaryType = 'arraybuffer';
  socket.onopen = () => { state = 'live'; readout(); };
  socket.onclose = (event) => {
    ctl = { state: 'none', available: false, reason: 'not connected' };
    updatePanel();
    if (event.code === 4401) {          // the instrument unpaired this page
      state = 'disconnected: scan the code on the instrument again';
      readout();
      return;
    }
    state = 'waiting for the server...';
    readout();
    setTimeout(retry, 1000);
  };
  socket.onerror = () => socket.close();
  socket.onmessage = (event) => {
    if (typeof event.data === 'string') {       // a note from the server
      try { note(JSON.parse(event.data)); } catch (error) { /* ignore */ }
      return;
    }
    pending = event.data;
    if (!drawing) draw();
  };
}

// A message is a 4 byte header length (big endian), the header (JSON), and
// the frame (JPEG).  Anything drawn over the frame belongs in the header, so
// that it is drawn on the frame that it describes.
async function draw() {
  drawing = true;
  while (pending !== null) {
    const data = pending;
    pending = null;
    const n = new DataView(data).getUint32(0);
    const text = new TextDecoder().decode(new Uint8Array(data, 4, n));
    const blob = new Blob([new Uint8Array(data, 4 + n)],
                          { type: 'image/jpeg' });
    try {
      const bitmap = await createImageBitmap(blob);
      if (canvas.width !== bitmap.width || canvas.height !== bitmap.height) {
        canvas.width = bitmap.width;
        canvas.height = bitmap.height;
      }
      ctx.drawImage(bitmap, 0, 0);
      bitmap.close();
      head = JSON.parse(text);
      shown += 1;
    } catch (error) {
      // a frame that cannot be decoded is skipped
    }
  }
  drawing = false;
  readout();
}

// ---- Controls -----------------------------------------------------------
// The server sends the properties and what each allows ('hello'), who may
// change them ('control') and their values ('values').  The page asks; the
// server checks every value again and the operator decides who may set.

const panel = document.getElementById('panel');
const gear = document.getElementById('gear');
const statusText = document.getElementById('status');
const ask = document.getElementById('ask');
const rows = document.getElementById('rows');
let controls = [];
let ctl = { state: 'none', available: false, reason: '' };
const widgets = {};      // name -> { entry, input, out }
let busy = null;         // the property that a finger is moving
const SEND_EVERY = 100;  // ms between values sent while a slider moves
const lastSent = {};
const timers = {};

function send(message) {
  if (socket !== null && socket.readyState === 1) {
    socket.send(JSON.stringify(message));
  }
}

function note(message) {
  if (message.type === 'hello') {
    controls = message.controls;
    ctl = { state: message.state, available: message.available,
            reason: message.reason };
    buildPanel();
  } else if (message.type === 'control') {
    ctl = { state: message.state, available: message.available,
            reason: message.reason };
    updatePanel();
  } else if (message.type === 'values') {
    for (const name in message.values) showValue(name, message.values[name]);
  }
}

function fmt(value) {
  if (typeof value !== 'number') return String(value);
  return Number.isInteger(value) ? String(value)
                                 : String(parseFloat(value.toPrecision(4)));
}

// A slider that spans three decades or more is logarithmic.
function isLog(entry) {
  return entry.min > 0 && entry.max / entry.min >= 1000;
}

function toPosition(entry, value) {
  if (isLog(entry)) {
    return 1000 * Math.log(value / entry.min) /
           Math.log(entry.max / entry.min);
  }
  return value;
}

function fromPosition(entry, position) {
  let value = position;
  if (isLog(entry)) {
    value = entry.min * Math.pow(entry.max / entry.min, position / 1000);
  }
  return entry.type === 'int' ? Math.round(value) : value;
}

function makeInput(entry) {
  let input;
  if (entry.type === 'bool') {
    input = document.createElement('input');
    input.type = 'checkbox';
  } else if (entry.type === 'list') {
    input = document.createElement('select');
    for (const choice of entry.limits) {
      const option = document.createElement('option');
      option.textContent = choice;
      input.appendChild(option);
    }
  } else {
    input = document.createElement('input');
    if ('min' in entry && 'max' in entry) {
      input.type = 'range';
      if (isLog(entry)) {
        input.min = 0; input.max = 1000; input.step = 1;
      } else {
        input.min = entry.min; input.max = entry.max;
        input.step = entry.step ||
            (entry.type === 'int' ? 1 : (entry.max - entry.min) / 1000);
      }
    } else {
      input.type = 'number';
      if (entry.step) input.step = entry.step;
    }
  }
  return input;
}

function readInput(entry, input) {
  if (entry.type === 'bool') return input.checked;
  if (entry.type === 'list') return input.value;
  if (input.type === 'range') return fromPosition(entry, Number(input.value));
  return Number(input.value);
}

function writeInput(entry, input, value) {
  if (entry.type === 'bool') input.checked = Boolean(value);
  else if (entry.type === 'list') input.value = value;
  else if (input.type === 'range') input.value = toPosition(entry, value);
  else input.value = value;
}

function sendSet(name, value, now) {
  const wait = SEND_EVERY - (performance.now() - (lastSent[name] || 0));
  if (now || wait <= 0) {
    clearTimeout(timers[name]); delete timers[name];
    lastSent[name] = performance.now();
    send({ type: 'set', name: name, value: value });
  } else if (!(name in timers)) {         // the newest value goes out later
    timers[name] = setTimeout(() => {
      delete timers[name];
      const w = widgets[name];
      sendSet(name, readInput(w.entry, w.input), true);
    }, wait);
  }
}

function buildPanel() {
  rows.textContent = '';
  for (const key in widgets) delete widgets[key];
  for (const entry of controls) {
    const row = document.createElement('div');
    row.className = 'row';
    const label = document.createElement('label');
    const title = document.createElement('span');
    title.textContent = entry.name;
    const out = document.createElement('span');
    label.append(title, out);
    const input = makeInput(entry);
    input.setAttribute('aria-label', entry.name);
    input.addEventListener('pointerdown', () => { busy = entry.name; });
    input.addEventListener('input', () => {
      const value = readInput(entry, input);
      out.textContent = fmt(value);
      sendSet(entry.name, value, entry.type !== 'int' && entry.type !== 'float'
                                 || input.type === 'number');
    });
    input.addEventListener('change', () => {
      busy = null;
      sendSet(entry.name, readInput(entry, input), true);
    });
    row.append(label, input);
    rows.appendChild(row);
    widgets[entry.name] = { entry: entry, input: input, out: out };
    showValue(entry.name, entry.value);
  }
  gear.hidden = controls.length === 0;
  updatePanel();
}

function showValue(name, value) {
  const w = widgets[name];
  if (!w || busy === name) return;
  writeInput(w.entry, w.input, value);
  w.out.textContent = fmt(value);
}

const STATUS = {
  none: 'View only.',
  requested: 'Waiting for the operator to allow it...',
  granted: 'You are controlling the camera.',
  denied: 'The operator said no.',
  revoked: 'The operator took control back.'
};

function updatePanel() {
  if (!ctl.available) {
    const reason = ctl.reason || 'not available';
    statusText.textContent = 'View only: ' + reason + '.';
    ask.hidden = true;
  } else {
    statusText.textContent = STATUS[ctl.state] || STATUS.none;
    ask.hidden = false;
    ask.disabled = ctl.state === 'requested';
    ask.textContent = ctl.state === 'granted' ? 'Release control'
                                              : 'Ask to control';
  }
  const live = ctl.available && ctl.state === 'granted';
  for (const name in widgets) {
    widgets[name].input.disabled = !(live && widgets[name].entry.writable);
  }
}

ask.addEventListener('click', () => {
  if (ctl.state === 'granted') {
    send({ type: 'release' });
    ctl.state = 'none';
    updatePanel();
  } else {
    send({ type: 'request' });
  }
});
gear.addEventListener('click', () => { panel.hidden = !panel.hidden; });

setInterval(() => { rate = shown; shown = 0; readout(); }, 1000);
document.addEventListener('click', (event) => {
  if (event.target.closest('#panel, #gear')) return;
  hud.style.display = hud.style.display === 'none' ? '' : 'none';
});
document.addEventListener('visibilitychange', () => {
  if (!document.hidden && (socket === null || socket.readyState > 1)) {
    connect();
  }
});
connect();
</script>
</body>
</html>
'''

_STYLE = '''<style>
  body { margin: 0; min-height: 100vh; display: flex; align-items: center;
         justify-content: center; background: #000; color: #ddd;
         font: 18px/1.5 -apple-system, system-ui, sans-serif; }
  main { max-width: 22em; padding: 24px; text-align: center; }
</style>'''

_HEAD = ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
         '<meta name="viewport" content="width=device-width, '
         'initial-scale=1"><title>QVideo</title>' + _STYLE + '</head>')

#: What a browser sees before it is paired.
DENIED = (_HEAD + '<body><main><p>This video is private.</p>'
          '<p>Scan the QR code on the instrument with this device\'s '
          'camera.</p></main></body></html>')

#: What a browser sees when its code does not pair.
EXPIRED = (_HEAD + '<body><main><p>This code does not work.</p>'
           '<p>It may have expired.  Open the share window on the '
           'instrument and scan the new code.</p></main></body></html>')
