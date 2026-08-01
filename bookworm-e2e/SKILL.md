---
name: bookworm-e2e
description: Run or author Bookworm's e2e test suites correctly — which suites need the dev server, the two-stage offline runbook (a genuinely dead server), browser discovery, and the conventions a new suite must follow. Applies to the bookworm repo (github.com/enstw/bookworm) only. Use when running its tests, when a suite fails mysteriously, or when writing a new e2e test there.
user-invocable: true
---

# Bookworm e2e suites

The scripts in `scripts/` are the source of truth — this file holds only what
they cannot say: ordering, preconditions, and the dead-server dance.

## Preconditions

- A Chromium. `scripts/e2e-browser.mjs` resolves `BROWSER_BIN` → installed
  Brave/Chrome/chromium → playwright's headless shell. Bare box:
  `pnpm dlx playwright install chromium-headless-shell`.
- Server-backed suites need `pnpm run dev` running and the token exported:
  `ADMIN_TOKEN=<value from .dev.vars>`. If 8787 was busy, wrangler silently
  took 8788 — export `BOOKWORM_URL=http://localhost:8788` to follow it.
- Fresh checkout: `pnpm run db:init:local` first, or every table read 500s.

## Suite matrix

| suite | command | needs |
| --- | --- | --- |
| slug, worker-pool, push-crypto | `pnpm run test:slug` etc. | nothing (pure node) |
| vertical, bg | `pnpm run test:vertical` / `test:bg` | Chromium only (own static server) |
| admin, shelf-admin, push-api, tts-stream | `pnpm run test:admin` etc. | dev server + ADMIN_TOKEN |
| tts-stream | | also `ffmpeg` on PATH (builds its mp3 fixture) |
| **everything above** | `ADMIN_TOKEN=… pnpm test` | dev server + Chromium |
| offline | see runbook below | dev server, then NO server |

## The offline runbook (test:offline)

DevTools offline emulation does not reach service workers, so the offline
stage needs the server actually dead. Never fold this into one command.

1. `ADMIN_TOKEN=… node scripts/test-offline-e2e.mjs prime` — publishes the
   test book, verifies the implicit ±5 window, the ⇣ arm/disarm cycle in the
   reader and on the shelf, and eviction. Repeatable: it pins the reader's
   position back to chapter 0 itself.
2. **Stop the dev server — completely.** Killing the wrangler parent can
   leave `workerd` alive and still answering; verify with
   `curl -s -o /dev/null -w "%{http_code}" http://localhost:8787/api/books`
   and `lsof -ti :8787 | xargs kill` if it still says 200.
3. `node scripts/test-offline-e2e.mjs offline` — same browser profile, no
   server: the service worker must serve shell, manifest and chapters.
4. Restart `pnpm run dev` for whatever runs next.

Both stages print JSON; any `FAIL` marker in it means exit 1.

## Authoring a new suite

- Import the CDP client: `import { launch } from "./e2e-cdp.mjs"` →
  `{ evalJs, send, close, sessionId }`. Browser flags (window size, autoplay)
  go in `args`; a static server's cleanup goes in `onFail`.
- Keep `nav` settle times, `waitFor` loops and `finish` in the script — they
  are suite-specific and belong under review, not hidden in the helper.
- Poll with `waitFor(expr, pred)`; never a bare fixed sleep for a condition.
- Click **ids** (`#offlineBtn`), never titles or visible text — those move
  with the interface language. Book content (chapter titles) is fair game.
- Assert user-facing strings against both languages, or match the 中文
  default (`/載入失敗|Failed to load/`).
- Pick a fresh CDP port (934x) and a `/tmp/bookworm-<suite>-e2e-profile`;
  `rmSync` the profile at start unless the suite needs carried-over state
  (offline stage 2 deliberately keeps it).
- Wire it into `package.json` as `test:<name>`, and into the `test` chain
  only if it is single-command (the offline two-stage stays manual).
