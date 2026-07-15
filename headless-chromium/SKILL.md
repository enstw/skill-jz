---
name: headless-chromium
description: >-
  Provision a working user-space headless Chromium on a machine that has no
  usable browser — no root, no apt install, no snap. Use whenever browser
  automation, an e2e test, or a page render is needed and no Chromium/Chrome
  exists (or the existing one won't start: missing libnss3/libnspr4 libs,
  "No usable sandbox" errors, Ubuntu's snap-wrapped chromium failing in a
  container). Produces a self-contained BROWSER_BIN wrapper that
  browser-screenshot's shot.sh, raw-CDP scripts, and playwright-core all
  accept. Do not `sudo apt install chromium` (needs root; on Ubuntu it's a
  snap that breaks in containers) and do not hand-roll the download — one
  idempotent script handles discovery, lib extraction, and sandbox detection.
---

# Headless Chromium (user-space, root-free)

Get a browser binary that works for agent automation on any box — including
containers and phones-running-Linux where there's no root, no snap support,
and no preinstalled browser.

## Usage

```sh
eval "$(bash scripts/provision.sh)"   # sets BROWSER_BIN; idempotent, fast when already provisioned
"$BROWSER_BIN" --version
```

All diagnostics go to stderr; stdout is exactly one `export BROWSER_BIN=...`
line. `FORCE=1` rebuilds the wrapper. The wrapper (at
`~/.cache/headless-chromium/chrome`) bakes in everything the binary needs —
`LD_LIBRARY_PATH` for locally-extracted libs and `--no-sandbox` when the
kernel disallows unprivileged user namespaces — so consumers treat it as a
plain browser binary with zero environment setup.

## What provisioning does

1. **Find a binary**: `$BROWSER_BIN` override → system Chrome/Chromium/Brave →
   an already-downloaded playwright `headless_shell` → else download one with
   `pnpm dlx playwright install chromium-headless-shell` (~100 MB into
   `~/.cache/ms-playwright/`, no root).
1. **Fix missing libs without root**: `ldd` finds unresolved sonames
   (typically just `libnss3` + `libnspr4`); `apt download` + `dpkg -x`
   extracts them into `~/.cache/headless-chromium/libs/` — `apt download`
   needs no root.
1. **Probe the sandbox**: actually boots a devtools endpoint (a `--version`
   check proves nothing); if the kernel lacks unprivileged user namespaces
   (Android GKI kernels, Ubuntu 23.10+ AppArmor restriction), `--no-sandbox`
   is baked into the wrapper.

## Consumers

- **browser-screenshot skill**: `BROWSER_BIN="$BROWSER_BIN" shot.sh …` — its
  discovery honors the env var.
- **Raw CDP** (zero deps, node ≥22): spawn with
  `--headless=new --remote-debugging-port=<port> --user-data-dir=<profile>`,
  fetch `http://127.0.0.1:<port>/json/version`, drive over WebSocket.
  Working example: `bookworm/scripts/test-vertical-e2e.mjs`.
- **playwright-core**: `chromium.launch({ executablePath: BROWSER_BIN })`.
  Pin playwright-core to the version whose registry matches the downloaded
  shell build, or it will re-download and re-trip host validation.

## Traps this skill encodes (learned the hard way)

1. **Ubuntu's `apt install chromium` is a snap** — fails in containers, and
   needs root anyway. Never the answer here.
1. **`--version` succeeding ≠ a working browser** — sandbox failures only
   surface when a renderer boots, hence the devtools-endpoint probe.
1. **pnpm on some arches self-destructs**: a `package.json` with
   `devEngines.packageManager` + `onFail: "download"` makes pnpm re-exec a
   downloaded `@pnpm/exe` that can be a blank placeholder (arm64), dying with
   `pnpm: 1: This: not found`. Strip that block; also keep pnpm projects off
   tmpfs (store links break).
1. **Chrome 149+ removed one-shot `--headless --screenshot`/`--dump-dom`**
   (silent empty output) — drive CDP instead; see browser-screenshot.
