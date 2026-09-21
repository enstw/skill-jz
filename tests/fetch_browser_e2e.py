"""Self-contained real-browser checks against an invented loopback publisher.
Run with the test dependencies from AGENTS.md; no real login or external website.
"""
import io
import json
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from pypdf import PdfReader, PdfWriter

ROOT = Path(__file__).resolve().parents[1]
AUTH = ROOT / 'authenticated-fetch/scripts/assisted.py'
sys.path.insert(0, str(ROOT / 'robust-web-fetch/scripts'))
import fetch


def make_pdf(width):
    writer = PdfWriter()
    writer.add_blank_page(width=width, height=100)
    stream = io.BytesIO()
    writer.write(stream)
    return stream.getvalue()


class Publisher(BaseHTTPRequestHandler):
    submits = 0

    def log_message(self, *args):
        pass

    def do_POST(self):
        # Invented SSO: accepts one reader, and needs the code the form page fills in itself.
        Publisher.submits += 1
        form = parse_qs(self.rfile.read(int(self.headers.get('Content-Length', 0))).decode())
        good = (form.get('u'), form.get('p'), form.get('code')) == (['reader'], ['fixture-pass'], ['42'])
        # Like a real SSO, the form lives on another origin (localhost) and hands back a ticket.
        home = f'http://127.0.0.1:{self.server.server_port}'
        self.send_response(303)
        self.send_header('Location', home + '/sso/return?ticket=T' if good else '/sso/form;jsessionid=abc')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_GET(self):
        code, kind, cookie = 200, 'text/html', None
        signed_in = 'sso=ok' in self.headers.get('Cookie', '')
        ticket = self.path == '/sso/return?ticket=T'
        if ticket or (self.path.startswith('/sso/gate') and signed_in):
            self.send_response(302)
            self.send_header('Location', '/account')
            if ticket:
                self.send_header('Set-Cookie', 'sso=ok; HttpOnly; Path=/')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        if self.path.startswith('/sso/gate'):
            body = (f'<title>Terms</title><button id="ok" onclick="location.href='
                    f"'http://localhost:{self.server.server_port}/sso/form'" + '">OK</button>').encode()
        elif self.path.startswith('/sso/form'):
            body = (b'<title>Sign in</title><form method="post" action="/sso/auth"><input id="u" name="u">'
                    b'<input id="p" name="p" type="password"><input id="code" name="code" type="hidden">'
                    b'<button id="go">Sign in</button></form>'
                    b'<script>setTimeout(() => { document.getElementById("code").value = "42"; }, 400)</script>')
        elif self.path == '/account':
            body = b'<title>Signed in</title>' if signed_in else b'<title>Sign in</title>'
        elif self.path == '/login':
            cookie = 'library=fixture; Max-Age=3600; HttpOnly; Path=/'
            body = b'<title>Library session ready</title><a href="/pdf/1">PDF chapter 1</a><a href="/pdf/2">PDF chapter 2</a>'
        elif self.path == '/public.pdf':
            kind, body = 'application/pdf', make_pdf(303)
        elif self.path.startswith('/pdf/'):
            if 'library=fixture' not in self.headers.get('Cookie', ''):
                code, body = 403, b'<title>Sign in</title><input type="password">'
            else:
                kind = 'application/pdf'
                body = make_pdf(101 if self.path.endswith('1') else 202)
        elif self.path == '/challenge':
            body = b'<title>Just a moment...</title><p>Verify that you are human</p>'
        elif self.path == '/article':
            body = b'<title>Invented study</title><article><h1>Example findings</h1><p>This is a local fixture with readable article content.</p></article>'
        else:
            code, body = 404, b'<title>Missing chapter</title>'
        self.send_response(code)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(body)))
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(body)


def main():
    out = {}
    server = ThreadingHTTPServer(('127.0.0.1', 0), Publisher)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix='fetch-browser-e2e-') as temporary:
        directory = Path(temporary)
        profile = directory / 'profile'
        launched = False

        def check(name, condition, observed=None):
            out[name] = 'ok' if condition else f'FAIL: {observed}'
            if not condition:
                raise AssertionError(f'{name}: {observed}')

        def command(*args, expected=0):
            child = subprocess.run([sys.executable, str(AUTH), '--json', '--port', str(port), *map(str, args)],
                                   capture_output=True, text=True, timeout=60)
            command.raw = child.stdout + child.stderr
            check('command_' + str(args[0]) + '_' + str(len(out)), child.returncode == expected, child.stderr or child.stdout)
            return json.loads(child.stdout)

        try:
            value = command('launch', '--profile', profile, '--headless')
            launched = True
            check('launch', value['session']['status'] == 'launched', value)
            value = command('launch', '--profile', profile, '--headless')
            check('same_profile_reuses', value['session']['status'] == 'reused', value)
            command('launch', '--profile', directory / 'other', '--headless', expected=1)
            command('stop', '--profile', directory / 'other', expected=1)

            target = directory / 'paper.pdf'
            native = subprocess.run([sys.executable, str(ROOT / 'robust-web-fetch/scripts/fetch.py'),
                                     origin + '/public.pdf', str(target), '--json'],
                                    capture_output=True, text=True, timeout=30)
            value = json.loads(native.stdout)
            check('native_fetch_cli', native.returncode == 0 and value['method'] == 'curl-cffi'
                  and value['artifact'] == 'native_pdf'
                  and float(PdfReader(target).pages[0].mediabox.width) == 303, value)
            original = make_pdf(99)
            target.write_bytes(original)
            value = command('save', origin + '/pdf/1', target, expected=1)
            check('unauthenticated_preserves_existing', target.read_bytes() == original, value)
            command('open', origin + '/login')
            value = command('status')
            check('disconnect_preserves_tab', any(t['url'].endswith('/login') for t in value['tabs']), value)
            value = command('pdflink', '/login')
            check('pdf_discovery_preserves_live_host', [i['href'] for i in value['links']] == [origin + '/pdf/1', origin + '/pdf/2'], value)
            command('pdflink', 'no-such-tab', expected=1)
            value = command('save', origin + '/pdf/1', target)
            check('cookies_cross_command', value['pdf_pages'] == 1 and float(PdfReader(target).pages[0].mediabox.width) == 101, value)
            value = command('merge', target, origin + '/pdf/1', origin + '/pdf/2')
            check('complete_merge_in_order', value['complete'] and [float(p.mediabox.width) for p in PdfReader(target).pages] == [101, 202], value)
            complete = target.read_bytes()
            value = command('merge', target, origin + '/pdf/1', origin + '/missing', expected=1)
            check('missing_chapter_preserves_existing', target.read_bytes() == complete and value['missing'], value)
            value = command('merge', target, origin + '/pdf/1', origin + '/missing', '--allow-partial', expected=3)
            check('partial_explicit_status', value['status'] == 'partial' and not value['complete'] and len(PdfReader(target).pages) == 1, value)

            sites = directory / 'sites'
            sites.mkdir()
            secrets = {'open': 'fixture-pass', 'wrong': 'not-the-pass', 'good': 'fixture-pass'}
            for name, secret in secrets.items():
                (directory / name).write_text(f'# comment\nFX_USER=reader\nFX_PASS={secret}\n')
                (directory / name).chmod(0o644 if name == 'open' else 0o600)
                (sites / f'{name}.json').write_text(json.dumps({
                    'entry': origin + '/sso/gate?url={url}', 'default_url': origin + '/account',
                    'credentials': str(directory / name), 'user_key': 'FX_USER', 'pass_key': 'FX_PASS',
                    'dismiss': ['#ok'], 'user': '#u', 'password': '#p', 'submit': '#go',
                    'ready': 'document.getElementById("code").value !== ""', 'success_url': '/account$',
                    'wait': 5}))
            command('login', 'absent', '--sites', sites, expected=1)
            fresh = directory / 'vault' / 'fresh'
            recipe = json.loads((sites / 'good.json').read_text())
            (sites / 'fresh.json').write_text(json.dumps({**recipe, 'credentials': str(fresh)}))
            value = command('login', 'fresh', '--sites', sites, expected=1)
            check('login_creates_empty_private_template', fresh.stat().st_mode & 0o777 == 0o600
                  and 'FX_USER=\nFX_PASS=\n' in fresh.read_text() and Publisher.submits == 0, value)
            value = command('login', 'fresh', '--sites', sites, expected=1)
            check('login_reports_unfilled_template', 'empty FX_USER' in value['error'] and Publisher.submits == 0, value)
            value = command('login', 'open', '--sites', sites, expected=1)
            check('login_refuses_shared_credential_file', 'chmod 600' in value['error'] and Publisher.submits == 0, value)
            value = command('login', 'wrong', '--sites', sites, expected=1)
            check('login_single_submit_on_rejection', Publisher.submits == 1 and 'not retried' in value['error']
                  and '/sso/form' in value['error'] and 'jsessionid' not in value['error'], value)
            check('login_failure_hides_secret', 'not-the-pass' not in command.raw, 'secret echoed')
            value = command('login', 'good', '--sites', sites)
            check('login_fills_after_dismiss_and_ready', value['login_verified'] and not value['already_authenticated']
                  and value['final_url'] == origin + '/account' and Publisher.submits == 2, value)
            check('login_success_hides_secret', 'fixture-pass' not in command.raw, 'secret echoed')
            value = command('login', 'good', '--sites', sites)
            check('login_reuses_live_session', value['already_authenticated'] and Publisher.submits == 2, value)

            command('stop', '--profile', profile)
            launched = False
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                with socket.socket() as probe:
                    if probe.connect_ex(('127.0.0.1', port)) != 0:
                        break
                time.sleep(0.1)
            command('launch', '--profile', profile, '--headless')
            launched = True
            value = command('save', origin + '/pdf/2', target)
            check('profile_cookie_survives_restart', float(PdfReader(target).pages[0].mediabox.width) == 202, value)

            value = fetch.attempt_rendered_pdf(origin + '/article', str(target))
            check('rendered_artifact_label', value['artifact'] == 'rendered_pdf' and value['pdf_pages'] >= 1, value)
            printed = target.read_bytes()
            for route in ('/challenge', '/missing'):
                try:
                    fetch.attempt_rendered_pdf(origin + route, str(target))
                except (ValueError, RuntimeError):
                    pass
                else:
                    check('reject_' + route, False, 'accepted invalid page')
                check('render_failure_preserves_' + route, target.read_bytes() == printed)
        except Exception as error:
            out['error'] = 'FAIL: ' + str(error)
        finally:
            if launched:
                try:
                    command('stop', '--profile', profile)
                except Exception as error:
                    out['cleanup'] = 'FAIL: ' + str(error)
            server.shutdown()
            server.server_close()
    print(json.dumps(out, indent=2))
    return 1 if any(str(v).startswith('FAIL:') for v in out.values()) else 0


if __name__ == '__main__':
    raise SystemExit(main())
