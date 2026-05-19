---
name: fetch-blocked-pdf
description: Download PDFs or web pages that are blocked by CDNs like Cloudflare or Akamai. Use when curl or web_fetch fails with 403 Forbidden.
---

# Fetch Blocked PDF

This skill provides a robust method to download PDFs or web pages when standard tools (`curl`, `wget`, `web_fetch`) are blocked by CDNs (Content Delivery Networks) such as Cloudflare or Akamai (often returning 403 Forbidden errors).

## How to use

The skill bundles a Python script `scripts/fetch.py` that uses `curl-cffi` to impersonate a real browser's TLS fingerprint, bypassing most CDN blocks. If that fails, it can optionally use Playwright to render the page and extract its HTML as Markdown.

### Basic PDF Download

To download a blocked PDF, run the bundled script using `uv run`:

```bash
uv run <path-to-skill>/scripts/fetch.py <URL> <output-path.pdf>
```

### HTML Markdown Fallback

If the target is an HTML page disguised as a PDF or if the PDF download still fails, you can use the `--html-fallback` flag. This will use Playwright to render the page and save the main content as a Markdown file (changing the `.pdf` extension to `.md` automatically).

> **Note:** The first run of `--html-fallback` triggers a one-time Chromium download (~150MB) via `playwright install`.

```bash
uv run <path-to-skill>/scripts/fetch.py <URL> <output-path.pdf> --html-fallback
```

### Advanced: Wayback Machine

If both methods fail, consider searching the Internet Archive's Wayback Machine for a snapshot of the PDF or page, and download the archive URL instead.
