---
name: robust-web-fetch
description: Fetch web source material when ordinary curl, wget, or web_fetch is insufficient, including PDFs, HTML pages, text files, rendered pages, archives, CDN-blocked sources, and login-walled subscription content via a user-assisted browser session.
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

A fifth, **semi-automated** strategy lives in a separate script for the blocks automation alone cannot pass — login-walled subscription content and interactive CAPTCHAs. See *Tier 5: user-assisted authenticated browser* below.

## How to use

```bash
uv run <path-to-skill>/scripts/fetch.py <URL> <output-path.pdf>
```

Add `--html-fallback` to accept a Markdown rendering of the page (written as `.md`) when the PDF itself cannot be retrieved:

```bash
uv run <path-to-skill>/scripts/fetch.py <URL> <output-path.pdf> --html-fallback
```

Add `--skip-rendered-pdf` when you specifically need the origin PDF bytes rather than a browser-rendered PDF of the page. The older `--skip-print-pdf` spelling is still accepted as an alias.

Add `--skip-wayback` for JS-rendered SPAs whose archive snapshots capture only the server-side loading shell — the Wayback tier would otherwise "succeed" with a contentless file.

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

## Tier 5: user-assisted authenticated browser (`scripts/assisted.py`)

For blocks the four automated tiers *cannot* beat but a **human with credentials can**: institutional subscription paywalls (publisher content the user's university library licenses), login proxies such as **EZproxy** (`https://<proxy-host>/login?url=<publisher-url>`), and one-off interactive CAPTCHAs. This tier is semi-automated by design — the human does the login once, the agent does everything after.

How it works:

1. `launch` starts a **headed** Chromium-family browser (Chrome/Brave/Chromium/Edge autodetected) with a *dedicated persistent profile* and a CDP debugging port. It never touches the user's normal browser profile.
2. `open <url>` navigates to the login-wrapped URL. **The human logs in in the visible window.** The session persists in the profile, so later runs usually skip re-login.
3. The agent reconnects over CDP and drives the *same logged-in session*: `pdflink` scans a tab for PDF-ish links, `save` downloads one file, `merge` downloads a list of chapter PDFs and binds them into one file. Downloads go through the browser context's request API, which **shares the cookie jar** — the human's clearance applies to every request.

```bash
uv run <path-to-skill>/scripts/assisted.py launch
uv run <path-to-skill>/scripts/assisted.py open "https://ezproxy.example.edu/login?url=https://www.tandfonline.com/doi/full/10.1080/..."
# ── human logs in in the visible window ──
uv run <path-to-skill>/scripts/assisted.py status     # list open tabs — confirms login landed
uv run <path-to-skill>/scripts/assisted.py pdflink tandfonline
uv run <path-to-skill>/scripts/assisted.py save "https://....../doi/pdf/10.1080/..." out.pdf
uv run <path-to-skill>/scripts/assisted.py merge book.pdf <chapter-url-1> <chapter-url-2> ...
```

Field notes (verified against a real university EZproxy):

- **EZproxy rewrites hostnames** — `www.tandfonline.com` becomes `www-tandfonline-com.<proxy-host>`. After login, scrape links from the *live page* rather than constructing publisher URLs by hand; the rewritten host must be preserved.
- **Chaptered ebooks** (Cambridge Core, JSTOR, Oxford Academic) expose one PDF per chapter. Collect every chapter link from the book page (`pdflink`), then `merge`. `save`/`merge` auto-retry with `?acceptTC=true&coverpage=false` for JSTOR-style TOS interstitials.
- **Check access before scraping**: "Get access" / a price tag / "Your institution does not have access" on the landing page means the library doesn't license that title — no amount of automation helps; fall back to interlibrary loan.
- **Limits**: a few platforms (e.g. De Gruyter) run bot checks that flag even CDP-driven navigation in a real browser. Leave the tab open and ask the human to click through; once the page passes, the session requests usually work.
- PDFs are magic-byte verified, same as the automated tiers — an interstitial is never silently saved as a `.pdf`.

## What the automated tiers do NOT defeat

No *fully automated* local method beats these — `fetch.py` fails cleanly and says so:

- **Interactive CAPTCHA** (Turnstile / hCaptcha that needs a human action).
- **IP-reputation blocks** (your IP is flagged regardless of fingerprint).
- **Login-walled subscription content** (credentials required, not just fingerprints).

For all three, escalate to **tier 5 above** when a human with access is available. Failing that: a paid Web Unlocker service (ZenRows, ScrapFly, Bright Data Web Unlocker), or a manual Internet Archive search if the automated snapshot lookup missed.

## Beyond the tiers: locating a fetchable URL (2026-07-05 field notes)

The tiers assume you already hold a fetchable URL. Three techniques from real acquisition work sit *upstream* of the tiers — they change or discover the URL instead of attacking the block:

1. **Wayback CDX search when the cited URL is dead.** The availability API returns nothing useful for restructured sites (e.g. gov.cn now 302s old article URLs to its homepage). Query the CDX index directly and filter on URL fragments you can guess (a date, a content ID):

   ```
   http://web.archive.org/cdx/search/cdx?url=<domain>*&filter=original:.*<fragment>.*&collapse=urlkey&fl=original,timestamp,statuscode
   ```

   **Pick the snapshot contemporaneous with publication, not the newest.** A 2022 snapshot of a 2013 pbc.gov.cn page is a JS shell with no content; the 2013-12-05 snapshot has the full static text. Sites that later adopted JS rendering silently poison recent snapshots.

1. **Check Internet Archive *lending* status before promising "borrow from IA" as a fallback.** Post-Hachette, most scanned books report `lending___status = is_printdisabled` — not borrowable by normal accounts. Verify programmatically instead of assuming:

   ```
   https://archive.org/advancedsearch.php?q=title:(...)+AND+creator:(...)&fl[]=identifier,lending___status&output=json
   ```

   If it says `is_printdisabled`, the real fallback is interlibrary loan, not IA.

1. **Hunt the alternative open version before fighting the paywall.** Paywalled books and articles often have a legally open sibling the tiers never need to fight: the working-paper version of a book chapter (university repositories: SFU Summit, EUI Cadmus, SSRN), the journal-article version of a book's core argument (law journals host their own open PDFs), or an official primary source that supersedes the secondary one (central-bank white papers). Search `<author> <topic> working paper|SSRN|repository` first; a five-minute hunt beats a four-tier escalation that ends blocked anyway. Cite with the version actually used, noted as such.
