// Example e2e suite built on e2e-cdp.mjs — copy into scripts/, rename, adapt.
//
// This is the SELF-CONTAINED flavor: it serves ./public over its own static
// server, so the suite needs no running backend. For the SERVER-BACKED
// flavor, delete the server block, point BASE at your dev server, and honor
// an env override (e.g. MYAPP_URL) so the suite can follow a moved port.
//
// Runs under node ≥22 (native fetch/WebSocket).

import { createServer } from "node:http";
import { readFileSync, existsSync, rmSync } from "node:fs";
import { join, extname } from "node:path";
import { launch } from "./e2e-cdp.mjs";

const PORT = 9351;      // CDP port — unique per suite, so suites can coexist
const HTTP_PORT = 8991; // static server port — also unique per suite
const PROFILE = "/tmp/myapp-example-e2e-profile";
const ROOT = "public";

const MIME = {
  ".html": "text/html", ".js": "text/javascript",
  ".css": "text/css", ".json": "application/json",
};
const server = createServer((req, res) => {
  const path = req.url === "/" ? "/index.html" : req.url.split("?")[0];
  const file = join(ROOT, decodeURIComponent(path));
  if (existsSync(file)) {
    res.writeHead(200, { "content-type": MIME[extname(file)] ?? "application/octet-stream" });
    res.end(readFileSync(file));
  } else {
    res.writeHead(404);
    res.end();
  }
}).listen(HTTP_PORT);

rmSync(PROFILE, { recursive: true, force: true }); // fresh browser state
const { evalJs, send, close, sessionId } = await launch({
  port: PORT, profile: PROFILE, args: ["--window-size=900,700"],
  onFail: () => server.close(),
});

// suite-local helpers: settle times and polling stay HERE, in the reviewed
// script, never hidden inside the shared client
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const nav = async (url) => { await send("Page.navigate", { url }, sessionId); await sleep(1200); };
const waitFor = async (expr, pred, tries = 60) => {
  for (let i = 0; i < tries; i++) {
    const v = await evalJs(expr);
    if (pred(v)) return v;
    await sleep(500);
  }
  return await evalJs(expr); // last value, so the FAIL message shows it
};
const finish = async (out) => {
  console.log(JSON.stringify(out, null, 2));
  await close();
  server.close();
  process.exit(JSON.stringify(out).includes("FAIL") ? 1 : 0);
};

// --- the test ---

const out = {};
await nav(`http://localhost:${HTTP_PORT}/`);
out.title = await evalJs(`document.title`);
out.rendered = (await waitFor(`document.body.children.length`, (n) => n > 0)) > 0
  ? "ok" : "FAIL: body stayed empty";
await finish(out);
