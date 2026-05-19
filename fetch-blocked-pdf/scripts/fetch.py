# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "curl-cffi",
#     "camoufox[geoip]",
#     "markdownify",
# ]
# ///

"""Fetch URLs blocked by CDNs (Cloudflare / Akamai).

Escalates across three *independent* strategies rather than a ladder of
brittle patches — a defense that adapts to one does not break the others:

  1. curl-cffi  — cheap "fight": real browser TLS/HTTP-2 fingerprint, no JS.
                  Clears the passive-fingerprint majority of blocks.
  2. Wayback    — "sidestep": fetch an Internet Archive snapshot. One cheap
                  API call; beats even CAPTCHA / IP-reputation because the
                  origin is never touched. Fails only if not archived.
  3. camoufox   — strong "fight": anti-detect Firefox that passes
                  non-interactive JS challenges, then pulls the file with
                  the earned clearance cookies.

Residual ceiling (no local tier beats this): interactive CAPTCHA
(Turnstile/hCaptcha needing a human action) and IP-reputation blocks. The
only guaranteed bypass there is a paid Web Unlocker service.
"""

import argparse
import subprocess
import sys

from curl_cffi import requests
from markdownify import markdownify as md


def looks_like_pdf(content):
    # PDFs start with %PDF, occasionally after a few stray leading bytes.
    return b"%PDF" in content[:1024]


def is_pdf_target(output_path):
    return output_path.endswith(".pdf")


def save_ok(content, output_path):
    """Write bytes, enforcing the PDF magic-byte check for .pdf targets so a
    CDN HTML challenge page is never silently saved as a PDF."""
    if is_pdf_target(output_path) and not looks_like_pdf(content):
        return False
    with open(output_path, "wb") as f:
        f.write(content)
    return True


# --- Tier 1: curl-cffi -------------------------------------------------------

def fetch_with_curl_cffi(url, output_path):
    print(f"[1/3] curl-cffi (latest Chrome fingerprint) -> {output_path}")
    try:
        # "chrome" auto-resolves to curl-cffi's newest fingerprint, so this
        # stays current as the dependency is upgraded.
        response = requests.get(url, impersonate="chrome", timeout=30)
        if response.status_code != 200:
            print(f"      HTTP {response.status_code}.")
            return False
        content = response.content
        if is_pdf_target(output_path) and not looks_like_pdf(content):
            ct = response.headers.get("content-type", "unknown")
            print(f"      HTTP 200 but not a PDF (content-type: {ct}, "
                  f"{len(content)} bytes) — likely a CDN challenge page.")
            return False
        save_ok(content, output_path)
        print(f"      Success! {len(content)} bytes.")
        return True
    except Exception as e:
        print(f"      Error: {e}")
        return False


# --- Tier 2: Wayback Machine -------------------------------------------------

def fetch_from_wayback(url, output_path):
    print("[2/3] Wayback Machine snapshot lookup")
    try:
        avail = requests.get(
            "https://archive.org/wayback/available",
            params={"url": url}, timeout=20,
        ).json()
        snap = avail.get("archived_snapshots", {}).get("closest")
        if not snap or not snap.get("available") or snap.get("status") != "200":
            print("      No usable snapshot.")
            return False
        # Insert the `id_` identity modifier so we get the raw original bytes,
        # not the Wayback-wrapped HTML viewer.
        ts = snap["timestamp"]
        snap_url = snap["url"].replace(f"/web/{ts}/", f"/web/{ts}id_/", 1)
        print(f"      Snapshot {ts} — downloading raw copy.")
        r = requests.get(snap_url, timeout=30)
        if r.status_code != 200:
            print(f"      Snapshot fetch HTTP {r.status_code}.")
            return False
        if not save_ok(r.content, output_path):
            print("      Snapshot is not a PDF.")
            return False
        print(f"      Success! {len(r.content)} bytes from archive.")
        return True
    except Exception as e:
        print(f"      Error: {e}")
        return False


# --- Tier 3: camoufox --------------------------------------------------------

def fetch_with_camoufox(url, output_path, html_fallback):
    print("[3/3] camoufox (anti-detect browser, passes JS challenges)")
    try:
        from camoufox.sync_api import Camoufox
    except ImportError as e:
        print(f"      camoufox not available: {e}")
        return False

    # One-time patched-Firefox download (~150MB on first run).
    print("      Ensuring camoufox browser is installed "
          "(one-time ~150MB download on first run)...")
    # Use the *current* interpreter (the uv-resolved venv that already has
    # camoufox) — no dependency on `uv` or a `camoufox` script being on PATH,
    # and `camoufox fetch` itself resolves the right binary per OS/arch.
    try:
        subprocess.run([sys.executable, "-m", "camoufox", "fetch"],
                        check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"      camoufox fetch failed:\n{e.stderr or e.stdout}")
        return False

    try:
        with Camoufox(headless=True) as browser:
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60000)

            # Give a non-interactive JS challenge time to resolve and set its
            # clearance cookie, then pull the file with the earned context.
            for attempt in range(4):
                page.wait_for_timeout(4000)
                if not is_pdf_target(output_path):
                    break  # HTML target — go straight to extraction
                resp = page.context.request.get(url)
                if resp.ok:
                    body = resp.body()
                    if looks_like_pdf(body):
                        save_ok(body, output_path)
                        print(f"      Success! {len(body)} bytes via "
                              f"camoufox-earned cookies.")
                        return True
                print(f"      Challenge not cleared yet "
                      f"(attempt {attempt + 1}/4)...")

            if is_pdf_target(output_path) and not html_fallback:
                print("      Could not retrieve the PDF (interactive CAPTCHA "
                      "or IP-reputation block likely).")
                return False

            # HTML extraction path: an HTML target, or --html-fallback on a
            # PDF target that could not be downloaded.
            out = output_path[:-4] + ".md" if output_path.endswith(".pdf") else output_path
            html = page.evaluate(
                "document.querySelector('main') "
                "? document.querySelector('main').outerHTML "
                ": document.body.outerHTML"
            )
            with open(out, "w", encoding="utf-8") as f:
                f.write(md(html))
            print(f"      Success! Page extracted to {out} (Markdown).")
            return True
    except Exception as e:
        print(f"      Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Fetch URLs blocked by CDNs (Cloudflare/Akamai): "
                    "curl-cffi -> Wayback -> camoufox.")
    parser.add_argument("url", help="URL to fetch")
    parser.add_argument("output", help="Output file path")
    parser.add_argument(
        "--html-fallback", action="store_true",
        help="If the PDF can't be retrieved, accept a Markdown rendering of "
             "the page from the camoufox tier (writes .md) instead of failing.")
    args = parser.parse_args()

    if fetch_with_curl_cffi(args.url, args.output):
        return
    if fetch_from_wayback(args.url, args.output):
        return
    if fetch_with_camoufox(args.url, args.output, args.html_fallback):
        return

    print("\nAll tiers failed. The remaining gates (interactive CAPTCHA or "
          "IP-reputation) are not defeatable locally — use a paid Web "
          "Unlocker (ZenRows/ScrapFly/Bright Data) or try a manual Internet "
          "Archive search.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
