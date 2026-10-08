# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright>=1.40", "pypdf>=4", "markdownify"]
# ///
"""User-assisted authenticated PDF downloads, including EZproxy sessions."""
import argparse
import io
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Installed skills may be copied or symlinked. Resolve siblings, or accept an
# explicit discovery result; never assume a particular agent's home directory.
_override = os.environ.get('ROBUST_WEB_FETCH_SKILL')
_candidates = [Path(_override).expanduser()] if _override else [
    root / 'robust-web-fetch' for root in
    (Path(__file__).absolute().parents[2], Path(__file__).resolve().parents[2])]
for _candidate in _candidates:
    if (_candidate / 'scripts/fetch_common.py').is_file():
        sys.path.insert(0, str(_candidate / 'scripts'))
        break
else:
    raise SystemExit('robust-web-fetch skill missing; install it alongside authenticated-fetch '
                     'or set ROBUST_WEB_FETCH_SKILL to its directory')
from fetch_common import atomic_write, emit, pdf_pages, resolve_skill, result

DEFAULT_PORT = 18222
DEFAULT_PROFILE = Path.home() / '.cache' / 'assisted-fetch-profile'
DEFAULT_SITES = Path.home() / '.config' / 'authenticated-fetch' / 'sites'
HANDOFF_SETTLE = 3  # seconds a page must stay on the vendor host
DEFAULT_WIDTH = 1440  # narrow viewports hide search boxes behind menus
RECIPE_KEYS = ('entry', 'credentials', 'user_key', 'pass_key', 'user', 'password', 'submit', 'success_url')


def browser_command(args, command):
    skill = resolve_skill('browser-cdp', __file__)
    cmd = ['node', str(skill / 'scripts/session.mjs'), command,
           '--port', str(args.port), '--profile', str(Path(args.profile).expanduser().absolute())]
    if command == 'launch' and args.headless:
        cmd.append('--headless')
    child = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
    if child.returncode:
        raise RuntimeError(child.stderr.strip() or 'Browser session command failed')
    return json.loads(child.stdout)


def with_context(args, fn):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(f'http://127.0.0.1:{args.port}', timeout=10000)
        try:
            if not browser.contexts:
                raise RuntimeError('The browser has no persistent context')
            return fn(browser.contexts[0])
        finally:
            # On a CDP connection this detaches; it does not close the user's tabs.
            browser.close()


def cmd_open(args):
    def go(ctx):
        page = ctx.new_page()
        page.goto(args.url, wait_until='domcontentloaded', timeout=45000)
        return result('success', input_url=args.url, final_url=page.url,
                      method='open', title=page.title(), login_verified=False)
    return with_context(args, go)


def cmd_status(args):
    return with_context(args, lambda ctx: result('success', method='status', tabs=[
        {'url': page.url, 'title': page.title()} for page in ctx.pages]))


def cmd_pdflink(args):
    def go(ctx):
        pages = [page for page in ctx.pages if not args.substr or args.substr in page.url]
        if not pages:
            raise ValueError('No matching tab; inspect status and select the intended page')
        page = pages[-1]
        links = page.eval_on_selector_all('a[href]', '''els => els.map(a => ({
          href: a.href, text: (a.textContent||'').trim().slice(0,120)
        })).filter(l => /pdf|download|epdf|fulltext/i.test(l.href + ' ' + l.text))''')
        unique = {link['href']: link for link in links}
        return result('success', method='pdflink', final_url=page.url, links=list(unique.values()))
    return with_context(args, go)


def load_recipe(args):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', args.site):
        raise ValueError('Site names use letters, digits, "-" and "_" only')
    path = Path(args.sites).expanduser() / f'{args.site}.json'
    if not path.is_file():
        known = ', '.join(sorted(item.stem for item in path.parent.glob('*.json'))) or 'none'
        raise ValueError(f'No login recipe at {path} (available: {known}); see references/login-recipes.md')
    recipe = json.loads(path.read_text(encoding='utf-8'))
    missing = [key for key in RECIPE_KEYS if not recipe.get(key)]
    if missing:
        raise ValueError(f'Recipe {path} lacks: {", ".join(missing)}')
    return recipe


def read_credentials(recipe):
    path = Path(recipe['credentials']).expanduser()
    keys = (recipe['user_key'], recipe['pass_key'])
    manual = 'or sign in by hand in the open window'
    if not path.exists():
        # Leave an empty template so the user only types two values; O_EXCL never
        # overwrites, and the mode is set at creation rather than after a window.
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w', encoding='utf-8') as file:
            file.write(f'# SECRET. Keep mode 600; never print, paste, or commit.\n{keys[0]}=\n{keys[1]}=\n')
        raise ValueError(f'Created an empty credential file at {path}; fill {keys[0]} and {keys[1]}, {manual}')
    if not path.is_file():
        raise ValueError(f'{path} is not a regular file')
    if path.stat().st_mode & 0o077:
        raise ValueError(f'{path} is readable by other accounts; run chmod 600 on it, {manual}')
    values = dict(line.split('=', 1) for line in path.read_text(encoding='utf-8').splitlines()
                  if '=' in line and not line.lstrip().startswith('#'))
    found = tuple(values.get(key, '').strip() for key in keys)
    if not all(found):
        raise ValueError(f'{path} has an empty {keys[0]} or {keys[1]}; fill it, {manual}')
    return found


def cmd_recipes(args):
    # Answers "can login run unattended?" without a browser. It reports only whether the
    # two values are present, never the values, and never creates the template.
    sites = []
    for path in sorted(Path(args.sites).expanduser().glob('*.json')):
        entry = {'site': path.stem, 'configured': False}
        try:
            recipe = json.loads(path.read_text(encoding='utf-8'))
            missing = [key for key in RECIPE_KEYS if not recipe.get(key)]
            if missing:
                raise ValueError(f'recipe lacks: {", ".join(missing)}')
            file = Path(recipe['credentials']).expanduser()
            if not file.is_file():
                raise ValueError(f'no credential file at {file}')
            if file.stat().st_mode & 0o077:
                raise ValueError(f'{file} is readable by other accounts; run chmod 600 on it')
            values = dict(line.split('=', 1) for line in file.read_text(encoding='utf-8').splitlines()
                          if '=' in line and not line.lstrip().startswith('#'))
            if not all(values.get(recipe[key], '').strip() for key in ('user_key', 'pass_key')):
                raise ValueError(f'{file} has an empty {recipe["user_key"]} or {recipe["pass_key"]}')
            entry['configured'] = True
        except (OSError, ValueError) as error:
            entry['reason'] = str(error)
        sites.append(entry)
    return result('success', method='recipes', sites=sites)


def cmd_login(args):
    from playwright.sync_api import Error as BrowserError
    recipe = load_recipe(args)
    target = args.url or recipe.get('default_url', '')
    done = re.compile(recipe['success_url'])

    def bare(page):
        # Ask the live document: over a CDP attachment page.url can stay at the form's
        # POST address after a cross-site redirect chain. A gateway carries the target
        # in its query (?url=...), which would satisfy success_url before sign-in, and
        # ;jsessionid= path parameters are session tokens; neither belongs in a result.
        try:
            url = page.evaluate('location.href')
        except BrowserError:
            url = page.url
        parts = urlsplit(url)
        path = '/'.join(segment.split(';')[0] for segment in parts.path.split('/'))
        return urlunsplit(parts._replace(path=path, query='', fragment=''))

    gateway = urlsplit(recipe['entry'].replace('{url}', '')).hostname
    vendor = urlsplit(target).hostname
    vendor = vendor if vendor and vendor != gateway else None

    def reached(page, seconds, form=False):
        # Redirect chains detach frames mid-poll, so a browser error means "look again".
        deadline = time.monotonic() + seconds
        arrived = None
        while time.monotonic() < deadline:
            try:
                here = bare(page)
                if done.search(here):
                    return 'done'
                # Some gateways sign the vendor in by its own SSO and hand the page to the
                # vendor's unproxied host. A page that settles there was handed off; it is
                # not proof of entitlement, so the caller reports it unverified.
                if vendor and urlsplit(here).hostname == vendor:
                    arrived = arrived or time.monotonic()
                    if time.monotonic() - arrived >= HANDOFF_SETTLE:
                        return 'handoff'
                else:
                    arrived = None
                if form and page.locator(recipe['user']).first.is_visible():
                    return 'form'
                for selector in recipe.get('dismiss', []) if form else []:
                    if page.locator(selector).first.is_visible():
                        page.locator(selector).first.click()
            except BrowserError:
                pass
            time.sleep(0.3)
        return None

    def go(ctx):
        page = ctx.new_page()
        page.goto(recipe['entry'].replace('{url}', target), wait_until='domcontentloaded', timeout=45000)
        state = reached(page, 30, form=True)
        if state is None:
            raise RuntimeError(f'Neither the login form nor the signed-in site appeared; stopped at '
                               f'{bare(page)} ({page.title()!r}). Finish in the open window')
        if state == 'form':
            user, password = read_credentials(recipe)
            if recipe.get('ready'):
                page.wait_for_function(recipe['ready'], timeout=15000)
            try:
                page.locator(recipe['user']).first.fill(user)
                page.locator(recipe['password']).first.fill(password)
            except BrowserError:
                # Browser call logs can echo the filled value; never chain them.
                raise RuntimeError('Could not fill the login form; sign in by hand in the open window') from None
            # One submit per invocation. A retry loop here could lock the account.
            page.locator(recipe['submit']).first.click()
            after = reached(page, float(recipe.get('wait', 60)))
            if after == 'handoff':
                state = after
            elif after is None:
                raise RuntimeError(f'Stalled at {bare(page)} ({page.title()!r}) after one submit, which '
                                   'was not retried. Read the message on that page before blaming the '
                                   'credential: a rejected token or verification code usually means the '
                                   "form's own script had not finished and the recipe needs a `ready` "
                                   'expression. Otherwise check the credential file, or finish in the open window')
        final, title = bare(page), page.title()
        if state == 'handoff':
            # Left open: the vendor page is where entitlement is confirmed.
            return result('success', input_url=target, final_url=final, method='login', site=args.site,
                          title=title, login_verified=False, handed_off=True,
                          already_authenticated=False,
                          note='Gateway handed the session to the vendor host. Confirm the '
                               "institution's name or access on that page with `text`; do not re-run login")
        if state == 'done':
            page.close()  # nothing new to show; routine session checks must not pile up tabs
        return result('success', input_url=target, final_url=final, method='login', site=args.site,
                      title=title, login_verified=True, already_authenticated=state == 'done')
    return with_context(args, go)


def cmd_text(args):
    from playwright.sync_api import Error as BrowserError
    def go(ctx):
        opened = args.url.startswith(('http://', 'https://'))
        if opened:
            page = ctx.new_page()
            page.set_viewport_size({'width': args.width or DEFAULT_WIDTH, 'height': 900})
            page.goto(args.url, wait_until='domcontentloaded', timeout=45000)
        else:
            pages = [page for page in ctx.pages if args.url in page.url]
            if not pages:
                raise ValueError('No matching tab; inspect status and select the intended page')
            page = pages[-1]
            if args.width:
                page.set_viewport_size({'width': args.width, 'height': 900})
        try:
            # Catalogue pages render results with script after DOMContentLoaded.
            page.wait_for_timeout(args.settle * 1000)
            if args.fill:
                selector, value = args.fill
                box = page.locator(selector).first
                box.fill(value, force=True)
                box.press('Enter')
                try:
                    page.wait_for_load_state('domcontentloaded', timeout=30000)
                except BrowserError:
                    pass
                page.wait_for_timeout(args.settle * 1000)
            text = page.evaluate('document.body ? document.body.innerText : ""')
            here = page.evaluate('location.href')
            if here.startswith('chrome-error:'):
                raise RuntimeError('The page failed to load (browser error page); try again')
            pattern = re.compile(args.links) if args.links else None
            # Only links a reader can see: catalogues hide menus full of unrelated titles, and
            # in-page anchors (language switches, skip links) share the page URL.
            links = [] if pattern is None else list({link['href']: link for link in page.eval_on_selector_all(
                'a[href]', 'els => els.filter(a => a.getClientRects().length).map(a => '
                '({href: a.href, text: (a.textContent||"").trim().slice(0,120)}))')
                if link['href'].split('#')[0] != here.split('#')[0]
                and pattern.search(link['href'] + ' ' + link['text'])}.values())
            return result('success', input_url=args.url, final_url=here,
                          method='text', title=page.title(), text=text[:args.max],
                          truncated=len(text) > args.max, links=links)
        finally:
            if opened and not args.keep:
                page.close()  # reading must not pile up tabs in the shared session
    return with_context(args, go)


def fetch_pdf(ctx, url, accept_jstor_terms=False):
    candidates = [url]
    host = urlsplit(url).hostname or ''
    # EZproxy rewrites www.jstor.org to www-jstor-org.<proxy>. Restrict the
    # publisher-specific retry and require an explicit opt-in for its terms.
    jstor = host == 'jstor.org' or host.endswith('.jstor.org') or host.startswith(('www-jstor-org.', 'jstor-org.'))
    if accept_jstor_terms and jstor:
        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query.update(acceptTC='true', coverpage='false')
        candidates.append(urlunsplit(parts._replace(query=urlencode(query))))
    errors = []
    for candidate in candidates:
        response = None
        try:
            response = ctx.request.get(candidate, timeout=120000)
            if response.status != 200:
                raise ValueError(f'HTTP {response.status}')
            body = response.body()
            pages = pdf_pages(body)
            return body, {'final_url': response.url, 'pdf_pages': pages}
        except Exception as error:
            errors.append(str(error))
        finally:
            if response is not None:
                response.dispose()
    raise ValueError('; '.join(errors))


def cmd_save(args):
    def go(ctx):
        body, details = fetch_pdf(ctx, args.url, args.accept_jstor_terms)
        atomic_write(args.out, body)
        return result('success', input_url=args.url, output=args.out, method='authenticated',
                      artifact='native_pdf', complete=True, bytes=len(body),
                      validation='pdf_structure', **details)
    return with_context(args, go)


def cmd_merge(args):
    from pypdf import PdfWriter
    def go(ctx):
        writer = PdfWriter()
        chapters, missing, documents = [], [], []
        try:
            for url in args.urls:
                try:
                    body, details = fetch_pdf(ctx, url, args.accept_jstor_terms)
                    documents.append(body)
                    chapters.append({'input_url': url, **details})
                except Exception as error:
                    missing.append({'input_url': url, 'error': str(error)})
            if (missing and not args.allow_partial) or not chapters:
                return result('failed', method='authenticated-merge', missing=missing,
                              chapters=chapters, error='Required chapters missing; output left unchanged')
            buffer = io.BytesIO()
            for body in documents:
                writer.append(io.BytesIO(body))
            writer.write(buffer)
            body = buffer.getvalue()
            pages = pdf_pages(body)
            atomic_write(args.out, body)
            return result('partial' if missing else 'success', output=args.out,
                          method='authenticated-merge', artifact='native_pdf', complete=not missing,
                          chapters=chapters, missing=missing, pdf_pages=pages, bytes=len(body),
                          validation='pdf_structure')
        finally:
            writer.close()
    return with_context(args, go)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=DEFAULT_PORT)
    parser.add_argument('--json', action='store_true')
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('launch', 'stop'):
        command = sub.add_parser(name)
        command.add_argument('--profile', default=str(DEFAULT_PROFILE))
        if name == 'launch':
            command.add_argument('--headless', action='store_true', help='For unattended fixture tests only; no login window')
        command.set_defaults(fn=lambda args: result('success', method=args.command,
                                                    session=browser_command(args, args.command)))
    command = sub.add_parser('open')
    command.add_argument('url')
    command.set_defaults(fn=cmd_open)
    command = sub.add_parser('login')
    command.add_argument('site', help='Recipe name: <sites>/<site>.json')
    command.add_argument('url', nargs='?', help='One target URL; defaults to the recipe default_url')
    command.add_argument('--sites', default=str(DEFAULT_SITES), help='Recipe directory')
    command.set_defaults(fn=cmd_login)
    command = sub.add_parser('recipes', help='List site recipes and whether each has a usable credential file')
    command.add_argument('--sites', default=str(DEFAULT_SITES), help='Recipe directory')
    command.set_defaults(fn=cmd_recipes)
    sub.add_parser('status').set_defaults(fn=cmd_status)
    command = sub.add_parser('pdflink')
    command.add_argument('substr', nargs='?')
    command.set_defaults(fn=cmd_pdflink)
    command = sub.add_parser('text', help='Read a page (URL opens a new tab, else a tab-URL substring)')
    command.add_argument('url', help='URL to open, or a substring of an open tab\'s URL')
    command.add_argument('--fill', nargs=2, metavar=('SELECTOR', 'TEXT'),
                         help='Type TEXT into SELECTOR and press Enter, e.g. a catalogue search box')
    command.add_argument('--links', metavar='REGEX', help='Also list links whose URL or text matches')
    command.add_argument('--max', type=int, default=6000, help='Characters of page text to return')
    command.add_argument('--settle', type=float, default=4, help='Seconds to let scripts render')
    command.add_argument('--width', type=int, help=f'Viewport width; new tabs default to {DEFAULT_WIDTH}')
    command.add_argument('--keep', action='store_true', help='Leave a newly opened tab open')
    command.set_defaults(fn=cmd_text)
    command = sub.add_parser('save')
    command.add_argument('url')
    command.add_argument('out')
    command.add_argument('--accept-jstor-terms', action='store_true')
    command.set_defaults(fn=cmd_save)
    command = sub.add_parser('merge')
    command.add_argument('out')
    command.add_argument('urls', nargs='+')
    command.add_argument('--allow-partial', action='store_true')
    command.add_argument('--accept-jstor-terms', action='store_true')
    command.set_defaults(fn=cmd_merge)
    # Accept shared flags before OR after subcommands, as the old launch docs showed.
    for command in sub.choices.values():
        command.add_argument('--port', type=int, default=argparse.SUPPRESS)
        command.add_argument('--json', action='store_true', default=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error('port must be between 1 and 65535')
    try:
        value = args.fn(args)
    except Exception as error:
        value = result('failed', input_url=getattr(args, 'url', None), method=args.command, error=str(error))
    emit(value, args.json)
    if not args.json:
        for item in value.get('links', []):
            print(f'{item["href"]}  [{item["text"]}]')
        for item in value.get('sites', []):
            print(f'{item["site"]}  {"configured" if item["configured"] else "not configured: " + item["reason"]}')
        for item in value.get('tabs', []):
            print(f'{item["url"]}  |  {item["title"]}')
        if value.get('final_url'):
            print(value['final_url'])
        if value.get('note'):
            print(value['note'])
        if value.get('text'):
            print(f'{value["title"]}\n\n{value["text"]}' + ('\n[truncated]' if value['truncated'] else ''))
    return {'success': 0, 'failed': 1, 'partial': 3}[value['status']]


if __name__ == '__main__':
    raise SystemExit(main())
