'''The web page that :class:`~QVideo.lib.QWebScreen.QWebScreen` serves.

One self-contained page: no framework and nothing to install.  It opens a
WebSocket to ``/ws``, draws each frame on a canvas that fits the window, and
reconnects when the server goes away.  A frame that arrives while the
previous one is being decoded replaces it, so a slow tablet shows the newest
frame and never falls behind.  Tapping the page shows or hides the readout.
'''

__all__ = ['PAGE']

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
</style>
</head>
<body>
<canvas id="view" width="16" height="16"></canvas>
<div id="hud">connecting...</div>
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

function connect() {
  if (socket !== null && socket.readyState <= 1) return;   // already open
  const scheme = location.protocol === 'https:' ? 'wss://' : 'ws://';
  socket = new WebSocket(scheme + location.host + '/ws');
  socket.binaryType = 'arraybuffer';
  socket.onopen = () => { state = 'live'; readout(); };
  socket.onclose = () => {
    state = 'waiting for the server...';
    readout();
    setTimeout(connect, 1000);
  };
  socket.onerror = () => socket.close();
  socket.onmessage = (event) => {
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

setInterval(() => { rate = shown; shown = 0; readout(); }, 1000);
document.addEventListener('click', () => {
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
