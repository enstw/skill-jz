# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "playwright>=1.40",
#   "pypdf>=4",
# ]
# ///
"""Tier 5: user-assisted authenticated browser (semi-automated downloads).

For sources behind a *login* the human can pass but automation cannot:
institutional subscription proxies (EZproxy), publisher paywalls with
library access, one-off interactive CAPTCHAs.

Flow:
  1. `launch`  — start a HEADED Chromium-family browser with a dedicated
     persistent profile and a CDP port. The window is visible.
  2. `open <url>` — open the login-wrapped URL. The HUMAN logs in in the
     visible window; the session cookie lands in the persistent profile,
     so later runs usually skip re-login.
  3. The agent then drives the same logged-in session over CDP:
     `status` / `pdflink` / `save` / `merge`. Downloads made through
     `context.request` share the browser's cookie jar.

Usage:
  uv run assisted.py launch [--port 18222] [--profile DIR]
  uv run assisted.py open <url>              # open tab, report final URL+title
  uv run assisted.py status                  # list open tabs
  uv run assisted.py pdflink [<url-substr>]  # scan a tab (default: last) for PDF-ish links
  uv run assisted.py save <url> <out>        # GET with session cookies, save; verifies %PDF- magic
  uv run assisted.py merge <out> <url>...    # download each URL, merge into one PDF (chaptered ebooks)

All commands accept --port (default 18222).
"""
import argparse
import io
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

DEFAULT_PORT = 18222
DEFAULT_PROFILE = Path.home() / ".cache" / "assisted-fetch-profile"

BROWSERS = [  # first hit wins
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "google-chrome", "chromium", "chromium-browser", "brave-browser", "microsoft-edge",
]


def find_browser():
    for cand in BROWSERS:
        if cand.startswith("/"):
            if Path(cand).exists():
                return cand
        elif shutil.which(cand):
            return shutil.which(cand)
    sys.exit("No Chromium-family browser found. Install Chrome/Brave/Chromium.")


def cdp_alive(port):
    try:
        urllib.request.urlopen(f"http://localhost:{port}/json/version", timeout=2)
        return True
    except Exception:
        return False


def cmd_launch(args):
    if cdp_alive(args.port):
        print(f"CDP already listening on :{args.port} — reusing existing browser.")
        return
    profile = Path(args.profile).expanduser()
    profile.mkdir(parents=True, exist_ok=True)
    exe = find_browser()
    subprocess.Popen(
        [exe, f"--remote-debugging-port={args.port}", f"--user-data-dir={profile}",
         "--no-first-run", "--no-default-browser-check", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
    )
    for _ in range(30):
        if cdp_alive(args.port):
            print(f"Launched {exe}\nCDP on :{args.port}, profile {profile}")
            return
        time.sleep(0.5)
    sys.exit("Browser started but CDP port never came up.")


def with_context(args, fn):
    from playwright.sync_api import sync_playwright
    if not cdp_alive(args.port):
        sys.exit(f"No CDP on :{args.port}. Run `assisted.py launch` first.")
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://localhost:{args.port}")
        try:
            fn(browser.contexts[0])
        finally:
            browser.close()  # detaches CDP; the visible browser stays open


def cmd_open(args):
    def go(ctx):
        page = ctx.new_page()
        page.goto(args.url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2000)
        print("URL:  ", page.url)
        print("TITLE:", page.title())
    with_context(args, go)


def cmd_status(args):
    def go(ctx):
        for pg in ctx.pages:
            try:
                print(f"- {pg.url}  |  {pg.title()}")
            except Exception as e:
                print(f"- {pg.url}  |  <{e}>")
    with_context(args, go)


def cmd_pdflink(args):
    def go(ctx):
        want = args.substr or ""
        pages = [pg for pg in ctx.pages if want in pg.url] or ctx.pages
        page = pages[-1]
        print("scanning:", page.url)
        links = page.eval_on_selector_all(
            "a[href]",
            """els => els.map(a => ({href: a.href, text: (a.textContent||'').trim().slice(0,60)}))
                    .filter(l => /pdf|download|epdf|fulltext/i.test(l.href + ' ' + l.text))""",
        )
        seen = set()
        for l in links:
            if l["href"] not in seen:
                seen.add(l["href"])
                print(f"  {l['href']}  [{l['text']}]")
    with_context(args, go)


def fetch_pdf(ctx, url):
    """GET via the browser session; retry with common accept-TOS params."""
    for u in (url, url + ("&" if "?" in url else "?") + "acceptTC=true&coverpage=false"):
        r = ctx.request.get(u, timeout=120000)
        body = r.body()
        if r.status == 200 and body[:5] == b"%PDF-":
            return body, r
    return None, r


def cmd_save(args):
    def go(ctx):
        body, r = fetch_pdf(ctx, args.url)
        if body is None:
            body = r.body()
            Path(args.out).write_bytes(body)
            print(f"WARNING: not a PDF. HTTP {r.status} "
                  f"{r.headers.get('content-type','?')} {len(body)} bytes -> {args.out}")
            print("First bytes:", body[:60])
            sys.exit(1)
        Path(args.out).write_bytes(body)
        print(f"HTTP {r.status}  {len(body)} bytes -> {args.out}  (PDF magic OK)")
    with_context(args, go)


def cmd_merge(args):
    from pypdf import PdfWriter
    def go(ctx):
        writer, ok = PdfWriter(), 0
        for u in args.urls:
            name = u.rsplit("/", 1)[-1][:60]
            body, r = fetch_pdf(ctx, u)
            if body:
                writer.append(io.BytesIO(body))
                ok += 1
                print(f"  OK   {name}  {len(body)//1024} KB")
            else:
                print(f"  FAIL {name}  HTTP {r.status}")
        if not ok:
            sys.exit("Nothing merged.")
        with open(args.out, "wb") as f:
            writer.write(f)
        print(f"merged {ok}/{len(args.urls)} -> {args.out}")
    with_context(args, go)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("launch"); s.add_argument("--profile", default=str(DEFAULT_PROFILE)); s.set_defaults(fn=cmd_launch)
    s = sub.add_parser("open"); s.add_argument("url"); s.set_defaults(fn=cmd_open)
    s = sub.add_parser("status"); s.set_defaults(fn=cmd_status)
    s = sub.add_parser("pdflink"); s.add_argument("substr", nargs="?"); s.set_defaults(fn=cmd_pdflink)
    s = sub.add_parser("save"); s.add_argument("url"); s.add_argument("out"); s.set_defaults(fn=cmd_save)
    s = sub.add_parser("merge"); s.add_argument("out"); s.add_argument("urls", nargs="+"); s.set_defaults(fn=cmd_merge)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
