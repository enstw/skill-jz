---
name: authenticated-fetch
description: >-
  Retrieves PDFs through a user-authenticated browser session, including
  library EZproxy, institutional subscriptions, and interactive challenges.
  Opens a persistent visible login window, then discovers and downloads PDF
  links with the same cookies. Validates files and merges chapter PDFs with
  explicit missing-chapter results. Use when human login or existing library
  access is required; depends on browser-cdp and robust-web-fetch.
---

# Authenticated Fetch

The user signs in through a visible browser; the agent continues in that same
session. Credentials stay in the dedicated browser profile, because scripts
should not need the user's password or normal browser profile.

Requires `uv`, Node 22+, **browser-cdp**, and **robust-web-fetch**. The latter
provides shared validation and result helpers without running its unattended
strategies. Resolve skills through host discovery. Sibling installs and symlink
source siblings work automatically; otherwise set `BROWSER_CDP_SKILL` and
`ROBUST_WEB_FETCH_SKILL` to the discovered directories.

## Login and download

```bash
uv run <skill>/scripts/assisted.py launch
uv run <skill>/scripts/assisted.py open "https://<proxy-host>/login?url=<publisher-url>"
# The user signs in in the visible browser window.
uv run <skill>/scripts/assisted.py status
uv run <skill>/scripts/assisted.py pdflink <publisher-or-proxy-host>
uv run <skill>/scripts/assisted.py save "<actual-pdf-link>" paper.pdf --json
```

A dedicated session uses port `18222` and profile
`~/.cache/assisted-fetch-profile` by default, preserving the previous helper's
login state. `--port` works before or after every subcommand; `launch` and
`stop` accept `--profile`. Use a separate port and profile for simultaneous
accounts. An occupied port with a different profile is rejected, because
reusing it could operate on another task's session.

Browser lifecycle is handled by browser-cdp's `scripts/session.mjs`, without a
gstack dependency. Each open/status/download command **disconnects while
leaving the browser and tabs open**. End a session explicitly with:

```bash
uv run <skill>/scripts/assisted.py stop
```

Stop checks profile ownership before closing the browser; it retains the
profile for a later login. `launch --headless` exists for fixture testing;
use the default visible window when a person must log in.

An open page or `status` response does not prove authentication. Confirm that
the requested title is accessible. If it says “Get access” or the institution
does not license it, record the limitation and seek another authorized copy.

## EZproxy and chaptered books

- Preserve links from the live page: EZproxy rewrites publisher hostnames, so
  constructing unproxied PDF URLs by hand can lose the authenticated route.
- `pdflink <substring>` only scans a matching tab. A missing match fails rather
  than falling back to an unrelated tab.
- For chaptered books, collect the expected chapters in publication order and
  compare them with the table of contents before merging; the script can only
  verify the URLs supplied to it.

```bash
uv run <skill>/scripts/assisted.py merge book.pdf "<chapter-1>" "<chapter-2>" --json
```

All required chapters must download and parse. Missing or invalid chapters
return exit 1 and leave existing output unchanged. `--allow-partial` permits a
partial artifact, labels it `partial`, lists missing URLs, and exits **3** so a
caller cannot mistake it for a complete book. Preserve chapter-to-source
mapping when citing a merged document, because merged page numbers may differ
from the publisher's printed pages.

Read [references/publishers.md](references/publishers.md) for JSTOR terms
interstitials and platform-specific guidance. `--accept-jstor-terms` enables
that retry only when the user has agreed to the applicable terms; it is never
added to unrelated publishers' URLs.

## Results and limits

`--json` emits one object on stdout using robust-web-fetch's
`references/result-contract.md`. Successful downloads distinguish actual PDF
bytes from rendered pages; this skill only saves native PDF bytes. Failed
requests never write an HTML error body over a PDF. Files are parsed and
atomically replaced only after validation.

Transport success and PDF structure do not prove identity, expected book
coverage, or evidentiary support. Report those checks separately. On an
interactive challenge, leave the tab available for the user to finish; if
access remains unavailable, record the source as blocked.

The session transport uses Playwright's documented
[shared request cookies](https://playwright.dev/python/docs/api/class-apirequestcontext)
and [connected-browser disconnection](https://playwright.dev/python/docs/api/class-browser#browser-close).
