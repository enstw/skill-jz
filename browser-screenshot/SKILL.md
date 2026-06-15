---
name: browser-screenshot
description: Headless screenshot or rendered-DOM dump of any URL or local HTML/SVG file, hardened against the headless-browser cold-profile hang. Use when asked to screenshot a page, capture a rendered local file, grab a thumbnail for visual QA, or dump a page's rendered DOM — and especially when a naive headless Chrome/Brave command hangs, writes an empty file, or must run unattended in a script.
---

# Browser Screenshot

Capture a headless screenshot — or dump the rendered DOM — of any URL or local file, reliably and unattended. Generalized from a project capture script that kept hanging; this is the durable, any-project form.

## Why a skill, not a raw `--headless --screenshot`

A naive headless invocation hangs or returns nothing. The bundled `scripts/shot.sh` neutralizes three *independent* causes, so the capture is deterministic instead of flaky:

1. **Cold profile.** A fresh `--user-data-dir` makes the browser stall through first-run setup. The script reuses **one** persistent profile, so only the very first call is cold; every later call is warm and fast. (Using a new dir per call — the common mistake — makes *every* call hang.)
1. **No self-exit.** `--headless=new` writes the capture in ~2 s but then idles instead of quitting, so a naive run never returns. Every call is force-ended by a GNU `timeout` wrapper; the screenshot lands before the kill.
1. **Stale lock.** A killed run leaves `Singleton{Lock,Socket,Cookie}` in the profile; the next run stalls trying to reach the dead instance. The script deletes them before each launch (safe — runs are sequential and it reaps the profile's processes after each call).

The browser's *own* `--timeout` flag is a capture/settle delay, **not** a process kill, so it cannot prevent the hang on its own — the OS-level GNU `timeout` is what guarantees termination.

On top of those, three reliability guarantees make it deterministic unattended:

1. **Retry once.** An empty capture (the classic cold first call) is retried a single time — the shared profile is warm by then — so the *first* call no longer needs a manual re-run.
1. **Guard auto-scales with `--settle`.** `--guard` defaults to `ceil(settle/1000)+3` s, so raising `--settle` for a heavy page can never let the hard kill fire *before* the capture lands (the old footgun: bump settle, forget guard, get a silent empty file). Pass `--guard` only to override.
1. **Concurrency lock.** Parallel invocations serialize on a portable atomic `mkdir` lock (macOS has no `flock`) instead of corrupting the one shared profile; a crashed run's lock self-clears via its recorded PID.

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
| `--guard <sec>` | auto: `ceil(settle/1000)+3` | OS-level hard kill; auto-tracks `--settle`. Override only to force a value. |
| `BROWSER_BIN` | auto (Brave→Chrome→Chromium) | browser binary |
| `SHOT_PROFILE` | `/tmp/browser-shot-profile` | reused profile dir |

## Reading a page's self-check (`#debug`-style)

To read values a page computes for itself, have the page write them **synchronously** to `document.body.dataset.*` (before `load`), then:

```bash
<path-to-skill>/scripts/shot.sh --dump 'file:///path/index.html#debug' | grep -oE 'data-[a-z]+="[^"]*"'
```

`--dump-dom` captures at `load`, so values set in an async callback (e.g. `document.fonts.ready.then(...)`) may not appear — compute them synchronously where possible. Page `console.log` is **not** reachable: Brave routes it through the DevTools protocol, not stderr, so `--enable-logging` does not surface it.

## Requirements

- A Chromium-family browser. On macOS without Chrome, Brave works (`/Applications/Brave Browser.app`); set `BROWSER_BIN` otherwise.
- GNU `timeout` (`brew install coreutils` → `/opt/homebrew/bin/timeout`, or `gtimeout`).
- Must be `--headless=new` (plain `--headless` writes nothing) — already set by the script.
