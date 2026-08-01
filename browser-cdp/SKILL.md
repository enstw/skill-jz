---
name: browser-cdp
description: >-
  One skill for every headless-browser need: SEE a rendered page (screenshot,
  preview/visual-QA an HTML/CSS/SVG file you just wrote, rendered-DOM dump,
  computed values), DRIVE a page programmatically (automate, fill forms, run
  JS in a real browser, print to PDF, emulate devices, scrape a JS-rendered
  app that needs interaction), and PROVISION a working user-space Chromium
  where none exists (no root, containers, snap-broken chromium, missing
  libnss3/libnspr4) — all with zero npm dependencies and minimal env impact.
  Do not hand-roll a `--headless --screenshot` one-liner (Chrome/Brave 149+
  render but write NOTHING, silently), do not npm-install
  puppeteer/playwright, do not paste a fresh 50-line CDP WebSocket client,
  and do not `sudo apt install chromium` (root; snap breaks in containers) —
  the bundled scripts and templates already handle discovery, provisioning,
  endpoint polling, capture hardening, and teardown. Sibling: browser-e2e
  layers the e2e test method on this skill's client templates.
user-invocable: true
---

# browser-cdp — see, drive, and provision a headless Chromium anywhere

The foundation layer for programmatic browser work, from plain shell and
node (≥22 — native fetch/WebSocket): get a Chromium on any box, capture what
a page renders, drive it over the Chrome DevTools Protocol, tear it down
without a trace. No test framework, no npm dependency, no root, nothing
global mutated.

Three capabilities, pick by task:

1. **See a page** (screenshot / DOM dump / quick eval) → `scripts/shot.sh`,
   or the gstack daemon when installed (route selection below).
2. **Drive a page** (automation, PDF, emulation, multi-step scraping) →
   copy `templates/find-browser.mjs` + `templates/cdp-client.mjs`.
3. **No usable browser on the box** → `scripts/provision.sh` (idempotent,
   user-space, no root).

## Seeing a page

### Route selection (run first)

```bash
_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
B=""
[ -n "$_ROOT" ] && [ -x "$_ROOT/.claude/skills/gstack/browse/dist/browse" ] && B="$_ROOT/.claude/skills/gstack/browse/dist/browse"
[ -z "$B" ] && B="$HOME/.claude/skills/gstack/browse/dist/browse"
[ -x "$B" ] && echo "USE_DAEMON: $B" || echo "USE_FALLBACK"
```

`USE_DAEMON` → use the browse daemon: it's the one shared Chromium on the
box; don't spin up a second browser beside it. `USE_FALLBACK` → use
`scripts/shot.sh`; don't install gstack just for a screenshot.

### Daemon path (`$B`)

Auto-starts on first command and **holds page state between commands**:

```bash
$B viewport 1920x1080            # set size explicitly (skip only if you don't care)
$B goto https://example.com      # blocks until loaded — no extra wait needed
$B wait ".selector"              # only if content renders AFTER load; or --networkidle
$B screenshot /tmp/shot.png      # full page by default
```

Also: `$B html` / `$B html '#id'` (rendered DOM), `$B text` (cleaned text),
`$B js "<expr>"` (eval in the live page), `$B console` (page console output).

Learned-the-hard-way specifics:

1. **Full page by default** — `--viewport` for viewport-crop,
   `--selector '.card'` to crop to an element, `--clip x,y,w,h` for a region.
1. **`file://` is scoped** to `$PWD` and `/tmp` (macOS `$TMPDIR` under
   `/var/folders/...` is REJECTED). Copy stray files into `/tmp` first, or
   `$B load-html <file>` (same scoping).
1. **Retina is free**: `$B viewport 480x600 --scale 2` → 2× density.
1. **Etiquette**: never `$B stop`/`restart`/`disconnect` (the daemon may
   hold other work's tabs and logged-in sessions); don't pass `--headed` or
   `--proxy`; don't ship a second Chromium next to it.

### Fallback path: `scripts/shot.sh`

Drives a headless instance over CDP (one browser per batch, Bun CDP client
`scripts/cdp-shot.mjs`), hardened against cold-profile hangs, wedged
browsers, stale Singleton locks, and concurrent invocations; empty captures
retry once.

```bash
<skill>/scripts/shot.sh https://example.com                 # -> /tmp/shot-0.png
<skill>/scripts/shot.sh ./index.html --out /tmp/page.png    # one file, named output
<skill>/scripts/shot.sh a.html b.html c.html                # batch -> /tmp/shot-0..2.png
<skill>/scripts/shot.sh --dump ./index.html                 # rendered DOM to stdout
```

| Flag / env | Default | Meaning |
|---|---|---|
| `--out <path>` | `/tmp/shot-<n>.png` | output file (multi-input appends `-<n>`) |
| `--size WxH` | `1920x1080` | viewport |
| `--settle <ms>` | `2500` | wait before capture (async render, animations) |
| `--guard <sec>` | auto from settle | GNU-timeout hard kill per CDP call |
| `BROWSER_BIN` | auto | browser binary override |
| `SHOT_PROFILE` / `SHOT_PORT` | `/tmp/browser-shot-profile` / `9333` | reused profile / DevTools port |

Requires Bun, GNU `timeout` (`brew install coreutils`), `curl`. No browser?
shot.sh auto-provisions via `provision.sh`. For `#debug`-style self-checks:
`shot.sh --dump 'file:///path/index.html#debug' | grep -oE 'data-[a-z]+="[^"]*"'`
(write dataset values synchronously, before `load`, to be safe).

**Always `Read` the output PNG afterwards** — an unviewed screenshot is
invisible to you and the user.

## Driving a page

Copy both templates next to your script (self-contained as a pair):
`find-browser.mjs` resolves a binary (`BROWSER_BIN` → provisioned wrapper →
Brave/Chrome/chromium → playwright headless shell); `cdp-client.mjs`
launches and connects.

```js
import { launch } from "./cdp-client.mjs";

const { evalJs, send, close, sessionId } = await launch({
  port: 9377,                        // unique per script, so runs coexist
  profile: "/tmp/myjob-cdp-profile", // scratch profile, never the user's
  args: ["--window-size=1280,900"],  // extra browser flags as needed
});

await send("Page.navigate", { url: "https://example.com" }, sessionId);
await new Promise((r) => setTimeout(r, 1200));           // nav settle
const title = await evalJs(`document.title`);            // ask the page
await close();                                           // kills the browser
```

- `evalJs(expr)` — evaluate in-page with `awaitPromise`; page throws become
  script throws. The workhorse: read state, click via
  `document.querySelector(...).click()`, fill fields, await app promises.
- `send(method, params, sessionId)` — raw CDP for everything else:
  `Page.printToPDF`, `Page.captureScreenshot`, `Emulation.*` overrides,
  `Network.*`, `Page.addScriptToEvaluateOnNewDocument` (shim an API before
  the page loads).
- Poll with a `waitFor` loop for conditions; keep settle times and polling
  in your script, not in the shared client — they differ per job and must
  stay visible to review.

For e2e *test suites* (verdict contract, suite taxonomy, service-worker
offline rules), use the **browser-e2e** skill — it builds on these templates.

## No usable browser? Provision one

```sh
eval "$(bash scripts/provision.sh)"   # sets BROWSER_BIN; idempotent, fast when already provisioned
"$BROWSER_BIN" --version
```

Stdout is exactly one `export BROWSER_BIN=...` line (diagnostics on stderr);
`FORCE=1` rebuilds. What it does:

1. **Find a binary**: `$BROWSER_BIN` → system Chrome/Chromium/Brave → an
   already-downloaded playwright `headless_shell` → else download one with
   `pnpm dlx playwright install chromium-headless-shell` (~100 MB into
   `~/.cache/ms-playwright/`, no root).
1. **Fix missing libs without root**: `ldd` finds unresolved sonames
   (typically `libnss3` + `libnspr4`); `apt download` + `dpkg -x` extracts
   them into `~/.cache/headless-chromium/libs/` — no root needed.
1. **Probe the sandbox** by booting a real DevTools endpoint; if the kernel
   lacks unprivileged user namespaces (Android GKI, Ubuntu 23.10+ AppArmor),
   `--no-sandbox` is baked into the wrapper.

The wrapper lands at `~/.cache/headless-chromium/chrome` with everything
baked in, so every consumer — shot.sh, find-browser.mjs, playwright's
`executablePath` — treats it as a plain browser binary. Provision **once**;
discovery finds the wrapper from then on with zero env setup.

## Minimal-impact rules

- **Scratch profiles in /tmp**, `rmSync`'d at start unless you deliberately
  carry state (logins, service workers) across runs. Never touch the user's
  real browser profile.
- **Unique CDP port per script** so concurrent jobs coexist.
- **Always `close()`** (and kill on error paths) — a leaked headless
  Chromium is invisible and eats memory forever.
- **Nothing installed globally**: the only disk footprint is
  `~/.cache/ms-playwright/` and/or `~/.cache/headless-chromium/`, both
  plain-deletable.

## Traps

1. **Chrome/Brave 149+ removed one-shot `--headless --screenshot` /
   `--dump-dom`** — they render and write nothing, silently. Drive CDP.
1. **`--version` succeeding proves nothing** — sandbox and lib failures
   only surface when a renderer boots. Trust only a DevTools endpoint
   answering on `/json/version`.
1. **Ubuntu's `apt install chromium` is a snap** — needs root and breaks in
   containers. Never the answer; provision user-space instead. A present
   system chromium may still be broken — that's why discovery prefers the
   provisioned wrapper, which exists only if it was probed working.
1. **pnpm on some arches self-destructs**: `devEngines.packageManager` +
   `onFail: "download"` can re-exec a blank `@pnpm/exe` placeholder (arm64),
   dying with `pnpm: 1: This: not found`. Strip that block; keep pnpm
   projects off tmpfs.
1. **DevTools network emulation doesn't reach service workers** — for
   offline claims, kill the server for real (see browser-e2e).

## Note for script consumers

`genimage-canvas`'s `gen-image.sh` invokes `scripts/shot.sh` directly,
path-to-path — the `scripts/` directory stays shipped and functional
regardless of which route agents use. Do not remove it.
