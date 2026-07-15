---
name: browser-screenshot
description: >-
  Headless screenshot or rendered-DOM dump of any URL or local HTML/SVG file.
  Use whenever a task needs to SEE or read a rendered page: screenshot a page,
  preview/visual-QA an HTML/CSS/SVG file you just wrote, grab a thumbnail, or
  dump a page's rendered DOM or computed values. Do not hand-roll a `--headless
  --screenshot` one-liner or a puppeteer/playwright capture script — Chrome and
  Brave 149+ removed the one-shot capture flags (they render but write NOTHING,
  silently). Routes through the shared gstack browse daemon (`$B`) when
  installed — one persistent Chromium, ~100ms per command; falls back to the
  bundled shot.sh CDP pipeline when gstack is absent. One command, zero setup.
---

# Browser Screenshot

Capture a headless screenshot — or dump the rendered DOM — of any URL or local file, reliably and unattended.

## Route selection (run first)

```bash
_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
B=""
[ -n "$_ROOT" ] && [ -x "$_ROOT/.claude/skills/gstack/browse/dist/browse" ] && B="$_ROOT/.claude/skills/gstack/browse/dist/browse"
[ -z "$B" ] && B="$HOME/.claude/skills/gstack/browse/dist/browse"
[ -x "$B" ] && echo "USE_DAEMON: $B" || echo "USE_FALLBACK"
```

1. `USE_DAEMON` → use the browse daemon (next section). It's the one shared Chromium on the box; don't spin up a second browser beside it.
1. `USE_FALLBACK` → use the bundled `scripts/shot.sh` (section below). Don't install gstack just for a screenshot — the fallback is fully capable.

## Primary path: the gstack browse daemon

The daemon auto-starts on the first `$B` command and **holds page state between commands** — a capture is a short command sequence, not one mega-invocation:

```bash
$B viewport 1920x1080                 # set size explicitly (skip only if you don't care)
$B goto https://example.com
$B wait --load                        # or: $B wait --networkidle | $B wait ".selector"
$B screenshot /tmp/shot.png           # full page by default
```

**Always `Read` the output PNG afterwards** — without that the screenshot is invisible to you and the user.

### shot.sh → daemon mapping

| Old shot.sh form | Daemon equivalent |
|---|---|
| `shot.sh <url> --out <path>` | `$B goto <url>` then `$B screenshot <path>` |
| `--size WxH` | `$B viewport WxH` (add `--scale 2` for retina) |
| `--settle <ms>` | `$B wait ".selector"` / `--networkidle` / `--load` (preferred, deterministic); for a pure time settle, `sleep 2.5` between commands — state persists |
| `--dump` | `$B html` (full rendered HTML) or `$B html '#id'`; `$B text` for cleaned text |
| eval mode (`cdp-shot.mjs … eval`) | `$B js "<expr>"` one-liner, `$B eval <file.js>` for multi-line |
| batch (`shot.sh a b c`) | repeat goto/screenshot pairs, or pipe a JSON array to `$B chain` |

### Differences to know

1. **Full page by default.** `$B screenshot` captures the whole page; pass `--viewport` for the old viewport-crop behavior, `--selector '.card'` to crop to one element, `--clip x,y,w,h` for a region.
1. **`file://` is scoped.** `$B goto file://...` only accepts files under `$PWD` or `/tmp` (verified: macOS `$TMPDIR` under `/var/folders/...` is REJECTED — the daemon allows `/private/tmp` + cwd). To render an HTML/SVG file from elsewhere, copy it into `/tmp` first, or use `$B load-html <file>` (same scoping).
1. **Retina is free.** `$B viewport 480x600 --scale 2` then screenshot → 2× pixel density. Not possible with shot.sh.

### Reading a page's self-check (`#debug`-style)

To read values a page computes for itself (e.g. written to `document.body.dataset.*`):

```bash
$B goto 'file:///tmp/index.html#debug'
$B js "JSON.stringify(document.body.dataset)"
```

`$B js` runs in the live page, so async-set values (e.g. inside `document.fonts.ready.then(...)`) are readable after a `$B wait`. `$B console` shows the page's console output — something the fallback can't reach at all.

### Daemon etiquette

1. **Never `$B stop`, `$B restart`, or `$B disconnect`** — the daemon may hold other work's tabs, cookies, and logged-in sessions.
1. Don't pass `--headed` or `--proxy`; plain headless default `$B` is exactly right for rendering.
1. Don't `npm i puppeteer` / ship a second Chromium — route everything through `$B`.

## Fallback path: bundled `scripts/shot.sh` (no gstack)

**Why not a raw `--headless --screenshot`:** Brave/Chrome **149+** removed the one-shot capture flags — they render but write nothing (silent empty file, no error). `shot.sh` drives a headless instance over the DevTools Protocol instead (one browser per batch, tiny Bun CDP client `scripts/cdp-shot.mjs`), with cold-profile, wedged-browser, stale-lock, retry-once, and concurrency-lock hardening built in.

```bash
<path-to-skill>/scripts/shot.sh https://example.com                 # -> /tmp/shot-0.png
<path-to-skill>/scripts/shot.sh ./index.html --out /tmp/page.png    # one file, named output
<path-to-skill>/scripts/shot.sh a.html b.html c.html                # batch -> /tmp/shot-0..2.png
<path-to-skill>/scripts/shot.sh --dump ./index.html                 # rendered DOM to stdout
```

| Flag / env | Default | Meaning |
|---|---|---|
| `--out <path>` | `/tmp/shot-<n>.png` | output file (multi-input appends `-<n>`) |
| `--size WxH` | `1920x1080` | viewport |
| `--settle <ms>` | `2500` | wait before capture (lets entrance animations / async render finish) |
| `--guard <sec>` | auto: `ceil(settle/1000)+8` | OS-level hard kill per CDP call; auto-tracks `--settle` |
| `BROWSER_BIN` | auto (Brave→Chrome→Chromium) | browser binary |
| `BUN_BIN` | auto (`bun` on PATH, else `~/.bun/bin/bun`) | Bun runtime for the CDP client |
| `SHOT_PROFILE` | `/tmp/browser-shot-profile` | reused profile dir |
| `SHOT_PORT` | `9333` | DevTools remote-debugging port |

Requirements: a Chromium-family browser, [Bun](https://bun.sh), GNU `timeout` (`brew install coreutils`), `curl`. For `#debug`-style self-checks under this path: `shot.sh --dump 'file:///path/index.html#debug' | grep -oE 'data-[a-z]+="[^"]*"'` (write dataset values synchronously, before `load`, to be safe).

## Note for script consumers

`genimage-canvas`'s `gen-image.sh` invokes `scripts/shot.sh` directly, path-to-path — the `scripts/` directory stays shipped and functional regardless of which route agents use. Do not remove it.
