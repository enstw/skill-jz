# /// script
# requires-python = ">=3.10"
# dependencies = ["curl-cffi", "camoufox[geoip]", "markdownify", "pypdf>=4"]
# ///
"""Fetch a known URL. Rendered PDFs and Markdown fallback require explicit flags."""
import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from fetch_common import atomic_write, emit, pdf_pages, prepare_document, resolve_skill, result, run_captured, validate_html

ARCHIVE_HEADERS = {'User-Agent': 'robust-web-fetch/2.0 (+https://archive.org)'}


def log(message):
    print(message, file=sys.stderr, flush=True)


def save_response(content, output, url, final_url, method, content_type='', snapshot_at=None):
    body, artifact, details = prepare_document(content, output, content_type)
    atomic_write(output, body)
    return result('success', input_url=url, output=output, method=method,
                  artifact=artifact, final_url=final_url, snapshot_at=snapshot_at,
                  complete=True, bytes=len(body), **details)


def attempt_tls_impersonation_download(url, output):
    from curl_cffi import requests
    response = requests.get(url, impersonate='chrome', timeout=30)
    if response.status_code != 200:
        raise ValueError(f'HTTP {response.status_code}')
    return save_response(response.content, output, url, response.url, 'curl-cffi',
                         response.headers.get('content-type', ''))


def get_archive_response(url, params=None):
    from curl_cffi import requests
    for attempt in range(2):
        response = requests.get(url, params=params, headers=ARCHIVE_HEADERS, timeout=20)
        if response.status_code == 200:
            return response
        if response.status_code == 429 and attempt == 0:
            try:
                pause = min(30, max(0, int(response.headers.get('Retry-After', '2'))))
            except ValueError:
                pause = 2
            log(f'Archive rate limit; waiting {pause}s')
            time.sleep(pause)
        else:
            raise ValueError(f'Archive HTTP {response.status_code}')
    raise ValueError('Archive rate limit')


def attempt_archive_snapshot(url, output, html_fallback=False):
    from curl_cffi import requests
    available = get_archive_response('https://archive.org/wayback/available', params={'url': url})
    snapshot = available.json().get('archived_snapshots', {}).get('closest')
    if not snapshot or not snapshot.get('available') or snapshot.get('status') != '200':
        raise ValueError('No usable archive snapshot')
    stamp = snapshot['timestamp']
    archived_url = snapshot['url'].replace(f'/web/{stamp}/', f'/web/{stamp}id_/', 1)
    response = requests.get(archived_url, headers=ARCHIVE_HEADERS, timeout=30)
    if response.status_code != 200:
        raise ValueError(f'Snapshot HTTP {response.status_code}')
    target = output
    if Path(output).suffix.lower() == '.pdf' and b'%PDF-' not in response.content[:1024] and html_fallback:
        target = str(Path(output).with_suffix('.md'))
    return save_response(response.content, target, url, response.url, 'wayback',
                         response.headers.get('content-type', ''), stamp)


def attempt_rendered_pdf(url, output):
    if Path(output).suffix.lower() != '.pdf':
        raise ValueError('Rendering requires a .pdf output')
    skill = resolve_skill('browser-cdp', __file__)
    # The browser only writes in scratch space; rejected pages never replace output.
    with tempfile.TemporaryDirectory(prefix='fetch-render-') as temporary:
        scratch = Path(temporary) / 'render.pdf'
        response = run_captured([
            'node', str(skill / 'scripts/session.mjs'), 'render',
            '--url', url, '--out', str(scratch),
        ], timeout=120)
        page = json.loads(response)
        validate_html(page['html'])
        # A native PDF viewer is not the source document.
        if 'application/pdf' in page['html'].lower():
            raise ValueError('Native PDF viewer; obtain the original PDF bytes')
        content = scratch.read_bytes()
        pages = pdf_pages(content)
        atomic_write(output, content)
        return result('success', input_url=url, output=output, final_url=page['final_url'],
                      method='browser-cdp', artifact='rendered_pdf', complete=True,
                      pdf_pages=pages, bytes=len(content), validation='page_screening+pdf_structure')


def camoufox_worker(url, output, html_fallback):
    from camoufox.sync_api import Camoufox
    with Camoufox(headless=True) as browser:
        page = browser.new_page()
        last_error = 'No document response'
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=45000)
        except Exception as error:
            # A native PDF can start a download instead of committing navigation.
            # The session request below still verifies status and actual bytes.
            last_error = str(error)
        for attempt in range(4):
            page.wait_for_timeout(2000)
            response = None
            try:
                response = page.context.request.get(url, timeout=15000)
                if response.status != 200:
                    raise ValueError(f'HTTP {response.status}')
                return save_response(response.body(), output, url, response.url, 'camoufox',
                                     response.headers.get('content-type', ''))
            except Exception as error:
                last_error = str(error)
            finally:
                if response is not None:
                    response.dispose()
        if Path(output).suffix.lower() != '.pdf' or html_fallback:
            target = str(Path(output).with_suffix('.md')) if Path(output).suffix.lower() == '.pdf' else output
            return save_response(page.content().encode(), target, url, page.url, 'camoufox', 'text/html')
        raise ValueError(last_error)


def attempt_antidetect_browser(url, output, html_fallback=False):
    # A subprocess deadline also covers browser startup; SIGALRM in Playwright's
    # event bridge could leave child processes running on a timeout.
    from camoufox.pkgman import installed_verstr
    try:
        installed_verstr()
    except (FileNotFoundError, ValueError):
        subprocess.run([sys.executable, '-m', 'camoufox', 'fetch'], check=True, timeout=180,
                       stdout=sys.stderr, stderr=sys.stderr)
    command = [sys.executable, __file__, url, output, '--camoufox-worker', '--json']
    if html_fallback:
        command.append('--html-fallback')
    return json.loads(run_captured(command, timeout=100))


def run(args):
    attempts = []
    steps = [('curl-cffi', lambda: attempt_tls_impersonation_download(args.url, args.output))]
    if not args.skip_wayback:
        steps.append(('wayback', lambda: attempt_archive_snapshot(args.url, args.output)))
    steps.append(('camoufox', lambda: attempt_antidetect_browser(args.url, args.output)))
    if args.rendered_pdf:
        steps.append(('browser-cdp', lambda: attempt_rendered_pdf(args.url, args.output)))
    # Exhaust native-document paths before accepting a Markdown substitute.
    if args.html_fallback and Path(args.output).suffix.lower() == '.pdf':
        if not args.skip_wayback:
            steps.append(('wayback-markdown', lambda: attempt_archive_snapshot(args.url, args.output, True)))
        steps.append(('camoufox-markdown', lambda: attempt_antidetect_browser(args.url, args.output, True)))
    for method, operation in steps:
        log(f'Trying {method}')
        try:
            value = operation()
            value['attempts'] = attempts + [{'method': method, 'status': 'success'}]
            return value
        except Exception as error:
            attempts.append({'method': method, 'status': 'failed', 'error': str(error)})
            log(f'{method}: {error}')
    return result('failed', input_url=args.url, attempts=attempts,
                  error='No acceptable document retrieved. Inspect attempt errors; '
                        'use authenticated-fetch for a known login or interactive challenge.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url')
    parser.add_argument('output')
    parser.add_argument('--html-fallback', action='store_true')
    parser.add_argument('--skip-wayback', action='store_true')
    rendering = parser.add_mutually_exclusive_group()
    rendering.add_argument('--rendered-pdf', action='store_true', help='Allow a screened web-page print after original-file attempts fail')
    rendering.add_argument('--skip-rendered-pdf', '--skip-print-pdf', action='store_true', help='Compatibility alias: rendering is already off by default')
    parser.add_argument('--json', action='store_true', help='One result object on stdout; progress goes to stderr')
    parser.add_argument('--camoufox-worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.camoufox_worker:
        try:
            from contextlib import redirect_stdout
            with redirect_stdout(sys.stderr):
                value = camoufox_worker(args.url, args.output, args.html_fallback)
        except Exception as error:
            log(str(error))
            return 1
    else:
        value = run(args)
    emit(value, args.json)
    return 0 if value['status'] == 'success' else 1


if __name__ == '__main__':
    raise SystemExit(main())
