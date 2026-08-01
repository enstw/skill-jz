---
name: browser-e2e
description: Give a web app a real-browser e2e test suite with zero test dependencies — plain node scripts driving a headless Chromium over CDP. Use when asked to "add e2e tests", "browser-test this app", "test this in a real browser", or when a change needs proof beyond unit tests. Do not npm-install playwright/puppeteer by default and do not paste a fresh 50-line CDP WebSocket client — the sibling browser-cdp skill's templates already handle browser discovery (Brave/Chrome/chromium/playwright-shell/provisioned wrapper), endpoint polling, evalJs, and teardown; this skill layers the e2e method (suite taxonomy, verdict contract, service-worker offline rules) on top, scaling from one smoke test to a multi-suite matrix. Depends on browser-cdp for the client templates.
user-invocable: true
---

# browser-e2e — hand-rolled CDP suites for web apps

A pattern for e2e-testing web apps with **no test framework and no npm
dependencies**: each suite is one plain node script (node ≥22 — native
fetch/WebSocket) that spawns a headless Chromium, drives it over the Chrome
DevTools Protocol, prints a JSON verdict, and exits 0/1. Proven shape: it
grew inside a PWA project to seven suites covering vertical typography,
service-worker offline, Web Push, and MediaSource audio.

## When this fits — and when it doesn't

Fits: dependency-averse repos; testing against the user's installed browser;
suites that need real browser state across separate invocations (service
workers, Cache API, localStorage); small teams where a bespoke 3-function
client is learnable in minutes.

Reach for playwright instead when: timing flakiness persists despite
event-driven waits, you need trace/video debugging, you want WebKit/Firefox
engines, or contributors expect standard tooling. (Playwright's WebKit is
still not iOS Safari — real device testing stays necessary either way.)

## Seeding a project

1. Copy `find-browser.mjs` and `cdp-client.mjs` from the sibling
   `browser-cdp` skill's `templates/` into the project's `scripts/` (or test
   dir). They are self-contained as a pair.
2. Copy this skill's `templates/test-example-e2e.mjs` next to them as the
   first suite; rename, adapt.
3. Wire `package.json`: one `test:<name>` per suite, and a `test` script
   chaining every suite that runs with a single command.
4. No browser on the machine? `pnpm dlx playwright install
   chromium-headless-shell` (discovery finds it). On locked-down/container
   boxes (no root, snap-broken chromium, missing libs) run the
   `browser-cdp` skill's `scripts/provision.sh` once instead — discovery
   also checks its wrapper (`~/.cache/headless-chromium/chrome`), so the
   suites work from then on with no env setup.

## The client

The client is browser-cdp's `cdp-client.mjs` — see that skill for the
general driving guidance; what matters for suites:

`launch({ port, profile, args, onFail })` →
`{ evalJs, send, close, sessionId, proc }`

- `evalJs(expr)` — evaluate in-page with `awaitPromise`; page throws become
  script throws. This is the workhorse: assert by asking the page.
- `send(method, params, sessionId)` — raw CDP for the rest: Emulation
  overrides, `Page.captureScreenshot`, `Page.addScriptToEvaluateOnNewDocument`
  (e.g. shimming an API the headless browser lacks).
- `args` — per-suite browser flags: `--window-size` (test at the geometry
  users actually have), `--autoplay-policy=no-user-gesture-required` for
  audio suites.
- `onFail` — cleanup if the browser never comes up (close your static server).

Keep `nav` settle times, `waitFor` loops, screenshots, and `finish` in each
suite script, not in the shared client — those are the parts that differ,
and hiding a 1200 ms vs 1500 ms settle in a helper is how timings drift
unreviewed.

## Suite taxonomy

Document which of these each suite is (a table in the project's CLAUDE.md or
a project skill — see below):

- **pure-node** — no browser at all (crypto, parsers, pools). Cheapest; put
  logic here whenever it can leave the page.
- **self-contained** — the suite runs its own static server over the app's
  public dir (see the template), plus synthetic fixtures. Runs anywhere,
  belongs in the single-command chain.
- **server-backed** — needs the real dev server and its secrets. Document
  the env contract (`ADMIN_TOKEN=…`, `MYAPP_URL=…` for moved ports).

## Conventions that keep suites honest

- **Verdict contract**: build one `out` object; every check writes `"ok"` or
  a `"FAIL: <observed value>"` string; `finish(out)` prints the JSON and
  exits 1 if `FAIL` appears anywhere. Greppable, diffable, self-explaining.
- **Poll, don't sleep, for conditions**: `waitFor(expr, pred)` at 500 ms; a
  bare `sleep` is only for nav settle. On timeout return the last value so
  the FAIL shows what the page actually said.
- **Click stable ids, never visible text or `title=`** — those move with the
  interface language. App *content* (fixture text) is fair game to assert.
- **i18n asserts match every language** the chrome ships, or pin the
  default: `/載入失敗|Failed to load/`.
- **Unique CDP port + `/tmp/<app>-<suite>-e2e-profile` per suite**, so suites
  coexist. `rmSync` the profile at start — *unless* the suite deliberately
  carries state across invocations (see below).
- **Screenshot on interesting states** (`Page.captureScreenshot` → /tmp):
  when a suite fails in CI logs, the picture answers first.

## Service workers, offline, and carried state

DevTools offline emulation (`Network.emulateNetworkConditions`, playwright's
`setOffline`) does **not** reach service workers — a SW-served app looks
offline-capable under emulation while being nothing of the sort. The only
honest offline test is two invocations of the same suite against the same
browser profile:

1. **prime** — server up: exercise the app so the SW and caches fill; verify
   cache contents via `evalJs` on the Cache API.
2. **Stop the server — completely.** Killing a dev-server wrapper can leave
   its worker process alive and answering; `curl` the port until it is dead,
   `lsof -ti :PORT | xargs kill` the stragglers.
3. **offline** — same profile, no server: the app must boot and work from
   the SW alone. Navigation outside the cached range must degrade, not crash.

Make the prime stage repeatable: reset any server-side state it depends on
(reading positions, fixtures) at the top, so counts don't drift between runs.

## Per-project runbook

This skill carries the method. Each project keeps its own thin runbook —
suite matrix, ports, env contract, quirks — in its CLAUDE.md or a project
skill, and points here for the rest. Exemplar: the bookworm reader
(github.com/enstw/bookworm) ships exactly that overlay in its repo as
`.claude/skills/e2e`.
