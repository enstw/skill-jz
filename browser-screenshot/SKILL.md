---
name: browser-screenshot
description: Headless screenshot or rendered-DOM dump of any URL or local HTML/SVG file, hardened against the headless-browser cold-profile hang. Use when asked to screenshot a page, capture a rendered local file, grab a thumbnail for visual QA, or dump a page's rendered DOM — and especially when a naive headless Chrome/Brave command hangs, writes an empty file, or must run unattended in a script.
---

# Browser Screenshot

Capture a headless screenshot — or dump the rendered DOM — of any URL or local file, reliably and unattended. Generalized from a project capture script that kept hanging; this is the durable, any-project form.

## Why a skill, not a raw `--headless --screenshot`

**The one-shot flags are gone.** Brave/Chrome **149+** removed the legacy headless capture commands — `--headless --screenshot` and `--dump-dom` now render but write nothing (silent empty file, no error). So `scripts/shot.sh` drives a headless instance over the **DevTools Protocol** instead: it launches ONE browser with `--remote-debugging-port` for the whole batch and captures each page with a tiny Bun CDP client (`scripts/cdp-shot.mjs`, `Page.captureScreenshot`). Bun is used only because it ships a native `WebSocket` + `fetch`, so the CDP client needs zero dependencies.

On top of that it neutralizes the classic flakiness, so capture is deterministic instead of flaky:

1. **Cold profile / slow startup.** It waits on the `/json/version` endpoint with `curl --retry` (no fixed `sleep`), and reuses **one** persistent profile so later runs are warm.
1. **Wedged browser.** Every CDP call is wrapped in a GNU `timeout`; the browser is reaped on exit by its unique `--remote-debugging-port`, so nothing is left running.
1. **Stale lock.** A killed run can leave `Singleton{Lock,Socket,Cookie}` in the profile; they're deleted before each launch.

Plus three reliability guarantees for unattended use:

1. **Retry once.** An empty capture is retried a single time (the browser is up by then), so a transient miss doesn't need a manual re-run.
1. **Guard auto-scales with `--settle`.** `--guard` defaults to `ceil(settle/1000)+8` s, so raising `--settle` for a heavy page can never let the hard kill fire *before* the capture lands. Pass `--guard` only to override.
1. **Concurrency lock.** Parallel invocations serialize on a portable atomic `mkdir` lock (macOS has no `flock`) instead of fighting over the one shared profile / debug port; a crashed run's lock self-clears via its recorded PID.

## How to use

```bash
<path-to-skill>/scripts/shot.sh https://example.com                 # -> /tmp/shot-0.png
<path-to-skill>/scripts/shot.sh ./index.html --out /tmp/page.png    # one file, named output
<path-to-skill>/scripts/shot.sh a.html b.html c.html                # batch -> /tmp/shot-0..2.png
<path-to-skill>/scripts/shot.sh --dump ./index.html                 # rendered DOM to stdout
```

Arguments are URLs or local paths (relative paths resolve against `$PWD`; bare paths become `file://`).

| Flag / env | Default | Meaning |
|---|---|---|
| `--out <path>` | `/tmp/shot-<n>.png` | output file (multi-input appends `-<n>`) |
| `--size WxH` | `1920x1080` | viewport |
| `--settle <ms>` | `2500` | wait before capture (lets entrance animations / async render finish) |
| `--guard <sec>` | auto: `ceil(settle/1000)+8` | OS-level hard kill per CDP call; auto-tracks `--settle`. Override only to force a value. |
| `BROWSER_BIN` | auto (Brave→Chrome→Chromium) | browser binary |
| `BUN_BIN` | auto (`bun` on PATH, else `~/.bun/bin/bun`) | Bun runtime for the CDP client |
| `SHOT_PROFILE` | `/tmp/browser-shot-profile` | reused profile dir |
| `SHOT_PORT` | `9333` | DevTools remote-debugging port |

## Reading a page's self-check (`#debug`-style)

To read values a page computes for itself, have the page write them **synchronously** to `document.body.dataset.*` (before `load`), then:

```bash
<path-to-skill>/scripts/shot.sh --dump 'file:///path/index.html#debug' | grep -oE 'data-[a-z]+="[^"]*"'
```

`--dump` reads the DOM *after* the same `--settle` wait as a screenshot, so values set in an async callback (e.g. `document.fonts.ready.then(...)`) **do** appear — synchronous is still safest, but the async ones are no longer lost. Page `console.log` is not reachable via stderr; if you need a computed value directly, the bundled CDP client also has an `eval` mode (`bun scripts/cdp-shot.mjs <endpoint> eval <url> '<jsExpr>' …`).

## Requirements

- A Chromium-family browser. On macOS without Chrome, Brave works (`/Applications/Brave Browser.app`); set `BROWSER_BIN` otherwise.
- [Bun](https://bun.sh) for the CDP client (native WebSocket + fetch, no npm deps); set `BUN_BIN` if not on `PATH`.
- GNU `timeout` (`brew install coreutils` → `gtimeout`) and `curl`.
