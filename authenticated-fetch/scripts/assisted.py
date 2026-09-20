# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright>=1.40", "pypdf>=4", "markdownify"]
# ///
"""User-assisted authenticated PDF downloads, including EZproxy sessions."""
import argparse
import io
import json
import os
import subprocess
import sys
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
    sub.add_parser('status').set_defaults(fn=cmd_status)
    command = sub.add_parser('pdflink')
    command.add_argument('substr', nargs='?')
    command.set_defaults(fn=cmd_pdflink)
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
        for item in value.get('tabs', []):
            print(f'{item["url"]}  |  {item["title"]}')
        if value.get('final_url'):
            print(value['final_url'])
    return {'success': 0, 'failed': 1, 'partial': 3}[value['status']]


if __name__ == '__main__':
    raise SystemExit(main())
