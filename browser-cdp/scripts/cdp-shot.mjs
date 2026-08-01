// CDP capture client for Brave/Chrome 149+, where the one-shot `--screenshot` /
// `--dump-dom` flags were removed. Driven by shot.sh, which launches the headless
// browser with --remote-debugging-port and feeds this script the endpoint.
//
// Run with Bun (native WebSocket + fetch, no deps):
//   bun cdp-shot.mjs <httpEndpoint> <shot|dump|eval> <navUrl> <outPath|jsExpr> <settleMs> <W> <H>
//     shot  -> writes a PNG to outPath
//     dump  -> prints document.documentElement.outerHTML to stdout (arg4 ignored)
//     eval  -> prints the value of the JS expression in arg4 to stdout
const [endpoint, mode, navUrl, outOrExpr, settleStr, wStr, hStr] = process.argv.slice(2);
const settle = parseInt(settleStr || '2500', 10), W = parseInt(wStr || '1920', 10), H = parseInt(hStr || '1080', 10);

const fail = (m) => { console.error('cdp-shot: ' + m); process.exit(1); };
let ver;
try { ver = await (await fetch(endpoint + '/json/version')).json(); } catch { fail('devtools endpoint unreachable'); }
const ws = new WebSocket(ver.webSocketDebuggerUrl);

let id = 0; const pending = new Map(); const handlers = [];
const send = (method, params, sessionId) =>
  new Promise((res) => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params: params || {}, sessionId })); });
const waitEvent = (method, sessionId, timeout = 15000) => new Promise((res, rej) => {
  const t = setTimeout(() => { off(); rej(new Error('timeout ' + method)); }, timeout);
  const h = (m) => { if (m.method === method && (!sessionId || m.sessionId === sessionId)) { off(); clearTimeout(t); res(m); } };
  handlers.push(h);
  function off() { const i = handlers.indexOf(h); if (i >= 0) handlers.splice(i, 1); }
});
ws.addEventListener('message', (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m.result); pending.delete(m.id); }
  else if (m.method) handlers.slice().forEach((h) => h(m));
});
await new Promise((res, rej) => { ws.addEventListener('open', res); ws.addEventListener('error', () => rej(new Error('ws'))); })
  .catch(() => fail('cannot open CDP websocket (need --remote-allow-origins=* on the browser)'));

const { targetId } = await send('Target.createTarget', { url: 'about:blank' });
const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true });
await send('Page.enable', {}, sessionId);
await send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: 1, mobile: false }, sessionId);
await send('Page.navigate', { url: navUrl }, sessionId);
try { await waitEvent('Page.loadEventFired', sessionId, 15000); } catch { /* capture whatever rendered */ }
await new Promise((r) => setTimeout(r, settle));   // settle: fonts + entrance animations

if (mode === 'dump' || mode === 'eval') {
  const expr = mode === 'dump' ? 'document.documentElement.outerHTML' : outOrExpr;
  const { result, exceptionDetails } = await send('Runtime.evaluate', { expression: expr, returnByValue: true }, sessionId);
  if (exceptionDetails) fail('eval threw: ' + (exceptionDetails.exception?.description || exceptionDetails.text));
  console.log(typeof result.value === 'string' ? result.value : JSON.stringify(result.value));
} else {
  const { data } = await send('Page.captureScreenshot', { format: 'png' }, sessionId);
  await Bun.write(outOrExpr, Buffer.from(data, 'base64'));
}
await send('Target.closeTarget', { targetId });
ws.close();
process.exit(0);
