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

def fetch_with_curl_cffi(url, output_path):
    print(f"Attempting to download with curl-cffi (impersonating Chrome) to {output_path}...")
    try:
        response = requests.get(url, impersonate="chrome110", timeout=30)
        if response.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(response.content)
            print(f"Success! Size: {len(response.content)} bytes.")
            return True
        else:
            print(f"curl-cffi failed with status code {response.status_code}.")
            return False
    except Exception as e:
        print(f"Error with curl-cffi: {e}")
        return False

def fetch_with_playwright(url, output_path):
    print("Attempting to extract HTML content using Playwright...")
    try:
        # Ensure browsers are installed
        subprocess.run(["uv", "run", "playwright", "install", "chromium"], check=True, capture_output=True)
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle")
            
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
