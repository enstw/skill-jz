---
name: bookworm-e2e
description: Project runbook for the e2e suites of the bookworm repo (github.com/enstw/bookworm) — which suites need the dev server, the two-stage offline runbook, and bookworm-specific conventions. Use when running its tests, when a suite fails mysteriously, or when writing a new e2e test there. The general method (CDP client, suite taxonomy, authoring rules) lives in the browser-e2e skill.
user-invocable: true
---

# Bookworm e2e suites

The project overlay for enstw/bookworm: only what is bookworm-specific lives
here. The method — the CDP client API, suite taxonomy, verdict contract,
service-worker testing rationale — is the `browser-e2e` skill; the scripts
in `scripts/` are the source of truth.

## Preconditions

- A Chromium: `scripts/e2e-browser.mjs` resolves `BROWSER_BIN` → installed
  Brave/Chrome/chromium → playwright's headless shell.
- Server-backed suites need `pnpm run dev` and `ADMIN_TOKEN=<value from
  .dev.vars>`. If 8787 was busy, wrangler silently took 8788 — export
  `BOOKWORM_URL=http://localhost:8788` to follow it.
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

Two invocations, same browser profile — the offline stage needs the server
genuinely dead (`browser-e2e` explains why emulation cannot substitute):

1. `ADMIN_TOKEN=… node scripts/test-offline-e2e.mjs prime` — publishes the
   test book, verifies the implicit ±5 window, the ⇣ arm/disarm cycle in the
   reader and on the shelf, and eviction. Repeatable: it pins the reader's
   position back to chapter 0 itself.
2. **Stop the dev server — completely.** Killing the wrangler parent can
   leave `workerd` alive and answering; curl the port and
   `lsof -ti :8787 | xargs kill` stragglers until it is dead.
3. `node scripts/test-offline-e2e.mjs offline` — no server: the service
   worker must serve shell, manifest and chapters; outside the cached window
   must degrade to the retry UI, not crash.
4. Restart `pnpm run dev` for whatever runs next.

## Bookworm-specific conventions

- CDP ports are 934x, profiles `/tmp/bookworm-<suite>-e2e-profile`; the
  offline stage-2 deliberately keeps its profile (that IS the test).
- The chrome is 中文 first: assert user-facing strings against both
  languages, e.g. `/載入失敗|Failed to load/`.
- 直排 suites run phone-shaped (`--window-size=430,900`) — a desktop-wide
  window puts the pager in a typographic regime readers never see.
- New suites join `package.json` as `test:<name>`; only single-command
  suites join the `pnpm test` chain (the offline two-stage stays manual).
