---
name: robust-web-fetch
description: Fetch web source material when ordinary curl, wget, or web_fetch is insufficient, including PDFs, HTML pages, text files, rendered pages, archives, and CDN-blocked sources.
---

# Robust Web Fetch

Fetch web source material when standard tools (`curl`, `wget`, `web_fetch`) are insufficient. This includes PDFs, HTML pages, text files, pages that need browser rendering, archived copies, and sources blocked by a CDN such as Cloudflare or Akamai — typically a 403, or an HTTP 200 "Just a moment…" challenge page.

## How it works

The bundled script `scripts/fetch.py` escalates through four *independent* strategies — not a ladder of brittle patches. Each attacks the block a different way, so a defense that adapts to one does not break the others:

1. **curl-cffi** — impersonates a real browser's TLS/HTTP-2 fingerprint. Cheap, no browser, clears the passive-fingerprint majority of blocks (most "curl gets 403" cases). No JavaScript.
1. **Wayback Machine** — one Internet Archive API call for an archived snapshot. The origin is never touched, so this beats even interactive CAPTCHA and IP-reputation blocks — but only if the document was archived.
1. **Rendered PDF** — loads the page in headless Chromium, waits for `networkidle`, and saves the rendered DOM through the browser's print-to-PDF API. Wins for SPAs whose content arrives via XHR after `domcontentloaded` (the case the camoufox tier's wait condition misses). Has no anti-detect, so an anti-bot CDN still blocks it — that case falls through to tier 4. Only runs for `.pdf` targets.
1. **camoufox** — an anti-detect Firefox that passes non-interactive JS challenges (the "Just a moment…" interstitial), then downloads the file with the earned clearance cookies.

The script stops at the first tier that produces a valid file. PDFs are verified by magic bytes, so a challenge page is never silently saved as a `.pdf`.

## How to use

```bash
uv run <path-to-skill>/scripts/fetch.py <URL> <output-path.pdf>
```

Add `--html-fallback` to accept a Markdown rendering of the page (written as `.md`) when the PDF itself cannot be retrieved:

```bash
uv run <path-to-skill>/scripts/fetch.py <URL> <output-path.pdf> --html-fallback
```

Add `--skip-rendered-pdf` when you specifically need the origin PDF bytes rather than a browser-rendered PDF of the page. The older `--skip-print-pdf` spelling is still accepted as an alias.

## Prerequisite: `uv`

The **only** thing that must exist before running this skill is [`uv`](https://docs.astral.sh/uv/) — it provisions a suitable Python, the pip deps, and (indirectly) the browser binary. Before running, check for it and install it only if missing (do not blindly reinstall):

```bash
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
```

That official installer is the agnostic default — the **same line works on macOS and Ubuntu** and needs no package manager (use the `wget -qO- https://astral.sh/uv/install.sh | sh` variant if `curl` is absent; on minimal Ubuntu, `apt-get install -y curl` first). Recommended platform alternatives if you prefer a package manager:

- **macOS:** `brew install uv`
- **Ubuntu:** `sudo snap install astral-uv --classic` (or the official script above)

## Agent- and OS-agnostic install

Past that one prerequisite, there is nothing else to install ahead of time, and the path is identical for any agent (Claude, Gemini, Codex) on any supported OS (macOS, Ubuntu):

- **Python deps** are declared inline (PEP 723 `# /// script` block). `uv run` reads them and builds an isolated ephemeral environment on first run — same command, same result on macOS and Linux. The only agent-facing interface is the `uv run …` shell command above; there is no agent-specific code or SDK.
- **The Chromium binary** (~170 MB) used by the rendered-PDF tier is not a pip package. The script fetches it on the first run that reaches tier 3 via `python -m playwright install chromium`, cached per-user (`~/Library/Caches/ms-playwright` on macOS, `~/.cache/ms-playwright` on Linux), so the download is one-time per machine.
- **The camoufox browser** (a patched Firefox, ~150 MB) is not a pip package. The script fetches it on the first run that reaches tier 4 via `python -m camoufox fetch`, invoked with the *same interpreter* `uv` already resolved — so it needs neither `uv` nor a `camoufox` script on `PATH`. `camoufox fetch` downloads the correct build for the host OS/arch and caches it per-user (`~/Library/Caches/camoufox` on macOS, `~/.cache/camoufox` on Linux), so the download is one-time per machine.

> **Linux Camoufox note:** Do not guess or maintain a broad Firefox dependency list here. If the camoufox tier fails to launch on Linux, check the official Camoufox installation guide first: <https://camoufox.com/python/installation/>. At the time this skill was written, the guide names this minimal Ubuntu command for fresh Linux installs:
>
> ```bash
> sudo apt install -y libgtk-3-0 libx11-xcb1 libasound2
> ```
>
> If using Camoufox's virtual-display mode, also check the official virtual display guide: <https://camoufox.com/python/virtual-display/>. Do not install `xvfb` unless using `headless="virtual"`.

## What this does NOT defeat

No local method beats these — the script fails cleanly and says so:

- **Interactive CAPTCHA** (Turnstile / hCaptcha that needs a human action).
- **IP-reputation blocks** (your IP is flagged regardless of fingerprint).

The only guaranteed bypass for those is a paid Web Unlocker service (ZenRows, ScrapFly, Bright Data Web Unlocker), or a manual Internet Archive search if the automated snapshot lookup missed.
