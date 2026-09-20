// Attached sessions disconnect without closing the browser. launch() owns its
// process and close() stops it; persistent sessions opt for disconnect().
import { spawn } from 'node:child_process';
import { findBrowser } from './find-browser.mjs';

export async function connect({ port, targetId, createTarget = true } = {}) {
  const endpoint = await fetch(`http://127.0.0.1:${port}/json/version`, {
    signal: AbortSignal.timeout(2000),
  }).then(r => r.json());
  const sock = new WebSocket(endpoint.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => { sock.close(); reject(new Error('CDP connect timed out')); }, 5000);
    sock.onopen = () => { clearTimeout(timer); resolve(); };
    sock.onerror = () => { clearTimeout(timer); reject(new Error('CDP connection failed')); };
  });
  let id = 0;
  const pending = new Map();
  const listeners = new Set();
  const rejectPending = () => {
    for (const { reject, timer } of pending.values()) {
      clearTimeout(timer); reject(new Error('CDP disconnected'));
    }
    pending.clear();
  };
  sock.onclose = rejectPending;
  sock.onerror = rejectPending;
  sock.onmessage = event => {
    const message = JSON.parse(event.data);
    if (message.method) {
      for (const listener of listeners) listener(message);
      return;
    }
    const call = pending.get(message.id);
    if (!call) return;
    pending.delete(message.id);
    clearTimeout(call.timer);
    if (message.error) call.reject(new Error(message.error.message));
    else call.resolve(message.result);
  };
  const send = (method, params = {}, sessionId) => new Promise((resolve, reject) => {
    const next = ++id;
    const timer = setTimeout(() => {
      pending.delete(next); reject(new Error(`CDP timed out: ${method}`));
    }, 60000);
    pending.set(next, { resolve, reject, timer });
    try { sock.send(JSON.stringify({ id: next, method, params, sessionId })); }
    catch (error) { clearTimeout(timer); pending.delete(next); reject(error); }
  });
  const disconnect = async () => {
    rejectPending();
    if (sock.readyState === WebSocket.CLOSED) return;
    await new Promise(resolve => {
      sock.addEventListener('close', resolve, { once: true });
      sock.close();
    });
  };
  let sessionId;
  let ownsTarget = false;
  try {
    if (!targetId && createTarget) {
      ({ targetId } = await send('Target.createTarget', { url: 'about:blank' }));
      ownsTarget = true;
    }
    if (targetId) {
      ({ sessionId } = await send('Target.attachToTarget', { targetId, flatten: true }));
      await send('Page.enable', {}, sessionId);
    }
  } catch (error) { await disconnect(); throw error; }
  const evalJs = async expression => {
    if (!sessionId) throw new Error('No page attached');
    const { result, exceptionDetails } = await send('Runtime.evaluate', {
      expression, returnByValue: true, awaitPromise: true,
    }, sessionId);
    if (exceptionDetails) throw new Error('page threw: ' +
      (exceptionDetails.exception?.description ?? exceptionDetails.text));
    return result.value;
  };
  const close = async () => {
    try { if (ownsTarget) await send('Target.closeTarget', { targetId }); }
    finally { await disconnect(); }
  };
  const onEvent = listener => { listeners.add(listener); return () => listeners.delete(listener); };
  return { send, evalJs, close, disconnect, onEvent, sessionId, targetId };
}

export async function launch({ port, profile, args = [], onFail, headed = false,
  persistent = false } = {}) {
  // Refuse occupied ports so close() cannot affect another job's browser.
  try {
    await fetch(`http://127.0.0.1:${port}/json/version`, { signal: AbortSignal.timeout(1000) });
    throw new Error(`CDP port ${port} is already in use; connect explicitly`);
  } catch (error) { if (error.message.includes('already in use')) throw error; }
  const { bin, env } = findBrowser({ headed });
  const proc = spawn(bin, [
    ...(headed ? [] : ['--headless=new']),
    `--remote-debugging-port=${port}`, '--remote-debugging-address=127.0.0.1',
    `--user-data-dir=${profile}`, '--no-first-run', '--no-default-browser-check',
    '--enable-automation', '--disable-dev-shm-usage', ...args,
  ], { stdio: 'ignore', env, detached: persistent });
  let spawnError;
  proc.on('error', error => { spawnError = error; });
  const deadline = Date.now() + 20000;
  try {
    while (Date.now() < deadline) {
      if (spawnError) throw spawnError;
      if (proc.exitCode !== null) throw new Error(`Browser exited: ${proc.exitCode}`);
      try {
        const connection = await connect({ port });
        if (persistent) proc.unref();
        const close = async () => {
          try { await connection.close(); }
          finally {
            if (proc.exitCode === null && proc.signalCode === null) {
              await new Promise(resolve => {
                const timer = setTimeout(() => proc.kill('SIGKILL'), 5000);
                proc.once('exit', () => { clearTimeout(timer); resolve(); });
                proc.kill();
              });
            }
          }
        };
        return { ...connection, close, proc };
      } catch (error) {
        if (Date.now() + 300 >= deadline) throw error;
        await new Promise(resolve => setTimeout(resolve, 300));
      }
    }
    throw new Error('Browser never came up');
  } catch (error) { proc.kill(); onFail?.(); throw error; }
}
