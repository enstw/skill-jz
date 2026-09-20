---
name: robust-web-fetch
description: >-
  Fetches a known web URL when ordinary downloads fail, including PDFs, HTML,
  text, archive copies, and CDN-blocked sources. Uses bundled download and
  validation scripts instead of improvised retry loops. Screens challenge
  pages, preserves existing files on failure, and reports artifact provenance
  as JSON. Use authenticated-fetch for EZproxy, institutional login, or a
  human-assisted challenge; rendered PDFs require an explicit option.
---

# Robust Web Fetch

Retrieve a **known URL** and report what was actually obtained. A successful
transport or parse does not establish document identity or support for a claim;
those remain the caller's source-audit task.

## Choose the route

- Ordinary fetch failed or returned a challenge page → run `scripts/fetch.py`.
- Known institutional login, EZproxy, or an interactive challenge → discover
  **authenticated-fetch** immediately; do not exhaust unattended retries first,
  because these require the user's existing access and interaction.
- Need a different copy or version of a work → read
  [references/find-alternatives.md](references/find-alternatives.md).
- Dead URL, archive timing, or platform-specific problems → read
  [references/source-notes.md](references/source-notes.md).

## Run

Requires `uv`. Python dependencies are declared in the script's PEP 723 header.

```bash
uv run <skill>/scripts/fetch.py <url> <output.pdf> --json
uv run <skill>/scripts/fetch.py <url> <output.md> --json
```

The original-document strategies are **curl-cffi → Wayback → Camoufox**. They
stop on the first validated output. PDF validation checks structure and page
count, not only a signature; HTML screening rejects recognized challenge,
login, and empty loading pages. Heuristics cannot recognize every access wall,
so inspect identity and completeness before treating the result as fulltext.

Additional options:

| Option | Meaning |
|---|---|
| `--skip-wayback` | Require a live copy, or skip archives known to contain loading shells |
| `--rendered-pdf` | After original-file attempts fail, permit a screened web-page print through browser-cdp; result is `rendered_pdf` |
| `--html-fallback` | After original-file and permitted print attempts fail, accept Markdown at the output's `.md` sibling |
| `--json` | Emit one result object to stdout; progress stays on stderr |

`--skip-rendered-pdf` and `--skip-print-pdf` remain accepted for existing callers;
rendering is now off by default. A rendered page can be an abstract, so explicit
opt-in prevents it from silently replacing the requested publisher PDF.

Output replacement is atomic and occurs only after validation. Failure leaves
existing output untouched. Exit 0 means an accepted artifact; exit 1 means all
applicable attempts failed. Error details distinguish HTTP, validation,
dependency, and browser failures; failure alone does not prove a paywall.

Read [references/result-contract.md](references/result-contract.md) when
integrating with a job queue or bibliography workflow. Record the actual output
path, method, artifact type, final URL, and archive timestamp. `content_verified`
is always false: acquisition is not an evidence audit.

## Browser dependencies

Camoufox is the specialized anti-detect Firefox strategy; its binary is fetched
on first use. Chromium discovery, provisioning, and printing belong to
**browser-cdp**, required only for `--rendered-pdf`. It runs without gstack.
Skills resolve sibling installations and symlink source siblings; for a separate
installation, set `BROWSER_CDP_SKILL` to the discovered skill directory. A missing
backend is reported as an attempt failure, never installed through another
provider silently.

Browser strategy processes have deadlines and clean up their owned children.
Wrap runs expected to take several minutes in the platform's bounded sleep
inhibitor, because first-use browser downloads can be slow.

## Compatibility

`scripts/assisted.py` now forwards to **authenticated-fetch** with unchanged
arguments. Install the new skill alongside this one, or set
`AUTHENTICATED_FETCH_SKILL` to its discovered directory. Missing dependencies
produce an actionable error; the old entry point does not contain a second
copy of the authenticated workflow.
