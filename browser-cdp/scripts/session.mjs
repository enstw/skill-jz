// Persistent headed sessions and one-shot rendering use the shared CDP client.
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { tmpdir } from 'node:os';
import { createServer } from 'node:net';
import { launch, connect } from '../templates/cdp-client.mjs';

async function availablePort() {
  const server = createServer();
  await new Promise((done, fail) => { server.once('error', fail); server.listen(0, '127.0.0.1', done); });
  const port = server.address().port;
  await new Promise(done => server.close(done));
  return port;
}

async function ownedConnection(port, profile) {
  const connection = await connect({ port, createTarget: false });
  try {
    const { arguments: args } = await connection.send('Browser.getBrowserCommandLine');
    if (!args.includes(`--user-data-dir=${resolve(profile)}`))
      throw new Error('CDP port belongs to a different profile; refusing to reuse or stop it');
    return connection;
  } catch (error) { await connection.disconnect(); throw error; }
}

async function main() {
  const [command, ...rest] = process.argv.slice(2);
  const options = {};
  for (let i = 0; i < rest.length; i++) {
    if (rest[i] === '--headless') options.headless = true;
    else if (['--port', '--profile', '--url', '--out'].includes(rest[i]) && rest[i + 1])
      options[rest[i].slice(2)] = rest[++i];
    else throw new Error(`Unknown or incomplete option: ${rest[i]}`);
  }
  const port = options.port ? Number(options.port) : await availablePort();
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('Invalid port');
  if (command === 'launch' || command === 'stop') {
    if (!options.profile || !options.port) throw new Error('launch/stop require --profile and --port');
    const profile = resolve(options.profile);
    if (command === 'stop') {
      const connection = await ownedConnection(port, profile);
      try { await connection.send('Browser.close'); }
      finally { await connection.disconnect(); }
      return { status: 'stopped', port, profile };
    }
    let listening = false;
    try {
      await fetch(`http://127.0.0.1:${port}/json/version`, { signal: AbortSignal.timeout(1000) });
      listening = true;
    } catch {}
    if (listening) {
      const connection = await ownedConnection(port, profile);
      await connection.disconnect();
      return { status: 'reused', port, profile };
    }
    mkdirSync(profile, { recursive: true, mode: 0o700 });
    const connection = await launch({ port, profile, headed: !options.headless, persistent: true });
    await connection.disconnect();
    return { status: 'launched', port, profile, pid: connection.proc.pid };
  }
  if (command === 'render') {
    if (!options.url || !options.out) throw new Error('render requires --url and --out');
    const profile = mkdtempSync(join(tmpdir(), 'browser-render-'));
    let connection;
    try {
      connection = await launch({ port, profile });
      const documents = new Map();
      connection.onEvent(message => {
        if (message.method === 'Network.responseReceived' && message.params.type === 'Document')
          documents.set(message.params.frameId, message.params.response);
      });
      await connection.send('Network.enable', {}, connection.sessionId);
      const navigation = await connection.send('Page.navigate', { url: options.url }, connection.sessionId);
      if (navigation.errorText) throw new Error(navigation.errorText);
      const deadline = Date.now() + 30000;
      let page;
      do {
        page = await connection.evalJs(`({ready:document.readyState, url:location.href,
          title:document.title, html:document.documentElement.outerHTML})`);
        if (page.ready === 'complete' && page.url !== 'about:blank') break;
        await new Promise(done => setTimeout(done, 250));
      } while (Date.now() < deadline);
      if (page.ready !== 'complete' || page.url === 'about:blank') throw new Error('Page did not finish loading');
      const response = documents.get(navigation.frameId);
      if (!response || response.status !== 200) throw new Error(`Document HTTP ${response?.status ?? 'unknown'}`);
      if (response.mimeType === 'application/pdf') throw new Error('Native PDF URL requires a byte download');
      // Wait for a stable DOM to give ordinary XHR-driven articles time to settle.
      let stable = 0;
      while (Date.now() < deadline && stable < 3) {
        await new Promise(done => setTimeout(done, 500));
        const next = await connection.evalJs(`({url:location.href,title:document.title,html:document.documentElement.outerHTML})`);
        stable = next.html === page.html ? stable + 1 : 0;
        page = next;
      }
      const { data } = await connection.send('Page.printToPDF', {
        printBackground: true, paperWidth: 8.27, paperHeight: 11.69,
      }, connection.sessionId);
      writeFileSync(options.out, Buffer.from(data, 'base64'));
      return { status: 'rendered', http_status: response.status, final_url: page.url,
        content_type: response.mimeType, title: page.title, html: page.html };
    } finally {
      if (connection) await connection.close();
      rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
    }
  }
  throw new Error('Usage: session.mjs launch|stop --port PORT --profile DIR [--headless]; render --url URL --out PDF');
}

try { console.log(JSON.stringify(await main())); }
catch (error) { console.error(error.message); process.exitCode = 1; }
