// Self-contained transport smoke: visible launch, attach, detach, and ownership.
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createServer } from 'node:net';
import { launch, connect } from '../browser-cdp/templates/cdp-client.mjs';

const out = {};
const profile = mkdtempSync(join(tmpdir(), 'browser-session-e2e-'));
const probe = createServer();
await new Promise(resolve => probe.listen(0, '127.0.0.1', resolve));
const port = probe.address().port;
await new Promise(resolve => probe.close(resolve));
let owned;
const check = (name, condition) => {
  out[name] = condition ? 'ok' : 'FAIL: condition false';
  if (!condition) throw new Error(name);
};
try {
  owned = await launch({ port, profile, headed: !process.argv.includes('--headless') });
  const info = await owned.send('Browser.getBrowserCommandLine');
  check('launch_mode', info.arguments.some(a => a.startsWith('--headless')) === process.argv.includes('--headless'));
  await owned.evalJs(`document.title = 'fixture session'`);
  const attached = await connect({ port, targetId: owned.targetId });
  check('attach_existing_tab', await attached.evalJs('document.title') === 'fixture session');
  await attached.close();
  check('attached_close_preserves_browser_and_tab', await owned.evalJs('document.title') === 'fixture session');
  const second = await connect({ port, targetId: owned.targetId });
  await second.disconnect();
  check('disconnect_preserves_tab', await owned.evalJs('document.title') === 'fixture session');
  let rejected = false;
  try { await launch({ port, profile }); }
  catch (error) { rejected = /already in use/.test(error.message); }
  check('occupied_port_rejected', rejected);
  check('original_still_usable', await owned.evalJs('document.title') === 'fixture session');
} catch (error) { out.error = 'FAIL: ' + error.message; }
finally {
  if (owned) {
    await owned.close();
    check('owned_close_stops_process', owned.proc.exitCode !== null || owned.proc.signalCode !== null);
  }
  rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
}
console.log(JSON.stringify(out, null, 2));
process.exitCode = Object.values(out).some(v => v.startsWith('FAIL:')) ? 1 : 0;
