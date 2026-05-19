# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "curl-cffi",
#     "playwright",
#     "markdownify"
# ]
# ///

import argparse
import sys
import subprocess
from curl_cffi import requests
from playwright.sync_api import sync_playwright
from markdownify import markdownify as md

def looks_like_pdf(content):
    # PDFs start with %PDF, occasionally after a few stray leading bytes. Be lenient.
    return b"%PDF" in content[:1024]

def fetch_with_curl_cffi(url, output_path):
    print(f"Attempting to download with curl-cffi (impersonating latest Chrome) to {output_path}...")
    try:
        # "chrome" auto-resolves to curl-cffi's latest supported fingerprint,
        # so this stays current as the dependency is upgraded — pinning an old
        # version is exactly what gets fingerprint-blocked.
        response = requests.get(url, impersonate="chrome", timeout=30)
        if response.status_code != 200:
            print(f"curl-cffi failed with status code {response.status_code}.")
            return False

        content = response.content
        content_type = response.headers.get("content-type", "").lower()

        # Cloudflare/Akamai challenge pages often return HTTP 200 with an HTML
        # body. Writing that to a .pdf is a silent failure, so when the output
        # is meant to be a PDF, require the body to actually be one.
        if output_path.endswith(".pdf") and not looks_like_pdf(content):
            print(
                f"Got HTTP 200 but the body is not a PDF "
                f"(content-type: {content_type or 'unknown'}, {len(content)} bytes) "
                f"— likely a CDN challenge/HTML page. Not saving."
            )
            return False

        with open(output_path, "wb") as f:
            f.write(content)
        print(f"Success! Size: {len(content)} bytes.")
        return True
    except Exception as e:
        print(f"Error with curl-cffi: {e}")
        return False

def fetch_with_playwright(url, output_path):
    print("Attempting to extract HTML content using Playwright...")
    try:
        # Ensure the Chromium browser is installed (one-time ~150MB download).
        print("Ensuring Chromium is installed (one-time ~150MB download on first run)...")
        try:
            subprocess.run(
                ["uv", "run", "playwright", "install", "chromium"],
                check=True, capture_output=True, text=True,
            )
        except subprocess.CalledProcessError as e:
            print(f"playwright install failed:\n{e.stderr or e.stdout}")
            return False

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            # networkidle is flaky on pages with analytics/long-polling; use a
            # bounded domcontentloaded wait so a hanging page can't block forever.
            page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Extract main content or body
            html_content = page.evaluate("document.querySelector('main') ? document.querySelector('main').outerHTML : document.body.outerHTML")
            markdown_text = md(html_content)
            
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(markdown_text)
                
            print(f"Success! HTML extracted and converted to Markdown at {output_path}.")
            browser.close()
            return True
    except Exception as e:
        print(f"Error with Playwright: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Fetch URLs blocked by CDNs (Cloudflare/Akamai)")
    parser.add_argument("url", help="URL to fetch")
    parser.add_argument("output", help="Output file path")
    parser.add_argument("--html-fallback", action="store_true", help="If PDF download fails, attempt to extract the page as Markdown using Playwright")
    args = parser.parse_args()

    success = fetch_with_curl_cffi(args.url, args.output)
    
    if not success and args.html_fallback:
        print("Falling back to Playwright HTML extraction...")
        # Change extension to .md if it was .pdf
        out_path = args.output
        if out_path.endswith('.pdf'):
            out_path = out_path[:-4] + '.md'
        fetch_with_playwright(args.url, out_path)
    elif not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
