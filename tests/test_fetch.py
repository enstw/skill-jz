"""Offline regression tests for acquisition integrity; no publisher access."""
import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from pypdf import PdfReader, PdfWriter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'robust-web-fetch/scripts'))
import fetch_common as common
import fetch

spec = importlib.util.spec_from_file_location('authenticated', ROOT / 'authenticated-fetch/scripts/assisted.py')
auth = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auth)


def pdf(width=100):
    writer = PdfWriter()
    writer.add_blank_page(width=width, height=100)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def response(body, status=200, url='https://example.test/file.pdf', kind='application/pdf'):
    return SimpleNamespace(status=status, status_code=status, body=lambda: body,
                           content=body, url=url, headers={'content-type': kind}, dispose=Mock())


class FetchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.out = Path(self.temporary.name) / 'paper.pdf'
        self.out.write_bytes(pdf(99))
        self.original = self.out.read_bytes()
        self.args = SimpleNamespace(url='https://example.test/file.pdf', out=str(self.out),
                                    accept_jstor_terms=False, allow_partial=False)

    def test_save_failure_preserves_existing_pdf(self):
        ctx = SimpleNamespace(request=SimpleNamespace(get=lambda *a, **kw: response(b'<html>login</html>', 403)))
        with patch.object(auth, 'with_context', side_effect=lambda args, fn: fn(ctx)):
            with self.assertRaises(ValueError):
                auth.cmd_save(self.args)
        self.assertEqual(self.out.read_bytes(), self.original)

    def test_save_rejects_corrupt_pdf_with_magic_header(self):
        ctx = SimpleNamespace(request=SimpleNamespace(get=lambda *a, **kw: response(b'%PDF-1.4 broken')))
        with patch.object(auth, 'with_context', side_effect=lambda args, fn: fn(ctx)):
            with self.assertRaises(ValueError):
                auth.cmd_save(self.args)
        self.assertEqual(self.out.read_bytes(), self.original)

    def merge(self, partial):
        self.args.urls = ['https://example.test/one', 'https://example.test/missing', 'https://example.test/two']
        self.args.allow_partial = partial
        def get(url, **kw):
            return response(b'error', 404) if url.endswith('missing') else response(pdf(101 if url.endswith('one') else 202), url=url)
        ctx = SimpleNamespace(request=SimpleNamespace(get=get))
        with patch.object(auth, 'with_context', side_effect=lambda args, fn: fn(ctx)):
            return auth.cmd_merge(self.args)

    def test_missing_chapter_leaves_output_untouched(self):
        value = self.merge(False)
        self.assertEqual(value['status'], 'failed')
        self.assertIsNone(value['output'])
        self.assertEqual(len(value['missing']), 1)
        self.assertEqual(self.out.read_bytes(), self.original)

    def test_explicit_partial_merge_preserves_order_and_reports_gap(self):
        value = self.merge(True)
        self.assertEqual(value['status'], 'partial')
        self.assertFalse(value['complete'])
        self.assertEqual([float(p.mediabox.width) for p in PdfReader(self.out).pages], [101, 202])
        self.assertEqual(value['missing'][0]['input_url'], 'https://example.test/missing')

    def test_all_missing_even_with_opt_in_leaves_output(self):
        ctx = SimpleNamespace(request=SimpleNamespace(get=lambda *a, **kw: response(b'error', 404)))
        self.args.urls = ['https://example.test/missing']
        self.args.allow_partial = True
        with patch.object(auth, 'with_context', side_effect=lambda args, fn: fn(ctx)):
            value = auth.cmd_merge(self.args)
        self.assertEqual(value['status'], 'failed')
        self.assertEqual(self.out.read_bytes(), self.original)

    def test_challenge_login_and_empty_shell_are_rejected(self):
        for html in ('<title>Just a moment...</title><p>Please wait</p>',
                     '<h1>Sign in</h1><input type="password">',
                     '<html><title>Publisher site</title><script>boot()</script><body></body></html>'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                common.prepare_document(html.encode(), 'page.md', 'text/html')

    def test_article_discussing_challenges_is_not_rejected(self):
        html = '<title>Research on access controls</title><article>Just a moment is a common challenge heading.</article>'
        body, artifact, _ = common.prepare_document(html.encode(), 'page.md', 'text/html')
        self.assertEqual(artifact, 'markdown')
        self.assertNotIn(b'<article>', body)

    def test_tls_html_challenge_never_overwrites_output(self):
        with patch('curl_cffi.requests.get', return_value=response(b'<title>Just a moment...</title>', kind='text/html')):
            with self.assertRaises(ValueError):
                fetch.attempt_tls_impersonation_download(self.args.url, str(self.out.with_suffix('.html')))
        self.assertFalse(self.out.with_suffix('.html').exists())

    def test_pdf_uppercase_extension_and_page_count(self):
        _, artifact, details = common.prepare_document(pdf(), 'FILE.PDF')
        self.assertEqual((artifact, details['pdf_pages']), ('native_pdf', 1))

    def test_camoufox_download_navigation_still_fetches_original_bytes(self):
        page = SimpleNamespace(goto=Mock(side_effect=RuntimeError('Download starting')),
                               wait_for_timeout=Mock(), context=SimpleNamespace(
                                   request=SimpleNamespace(get=lambda *a, **kw: response(pdf(123)))))
        browser = SimpleNamespace(new_page=lambda: page)
        fake = types.ModuleType('camoufox.sync_api')
        fake.Camoufox = lambda **kw: contextlib.nullcontext(browser)
        with patch.dict(sys.modules, {'camoufox.sync_api': fake}):
            value = fetch.camoufox_worker(self.args.url, str(self.out), False)
        self.assertEqual(value['artifact'], 'native_pdf')
        self.assertEqual(float(PdfReader(self.out).pages[0].mediabox.width), 123)

    def test_atomic_replace_failure_preserves_file_and_removes_temporary(self):
        with patch.object(common.os, 'replace', side_effect=OSError('disk error')):
            with self.assertRaises(OSError):
                common.atomic_write(self.out, pdf(200))
        self.assertEqual(self.out.read_bytes(), self.original)
        self.assertEqual(list(self.out.parent.iterdir()), [self.out])

    def test_default_route_does_not_print_or_fallback_early(self):
        args = SimpleNamespace(url=self.args.url, output=str(self.out), skip_wayback=False,
                               rendered_pdf=False, html_fallback=True)
        value = common.result('success', output=self.out, artifact='native_pdf', complete=True)
        with patch.object(fetch, 'attempt_tls_impersonation_download', side_effect=ValueError('blocked')), \
             patch.object(fetch, 'attempt_archive_snapshot', side_effect=ValueError('not PDF')) as archive, \
             patch.object(fetch, 'attempt_antidetect_browser', return_value=value), \
             patch.object(fetch, 'attempt_rendered_pdf') as render:
            actual = fetch.run(args)
        self.assertEqual(actual['artifact'], 'native_pdf')
        archive.assert_called_once_with(args.url, args.output)
        render.assert_not_called()

    def test_archive_result_records_provenance_and_markdown_path(self):
        available = SimpleNamespace(json=lambda: {'archived_snapshots': {'closest': {
            'available': True, 'status': '200', 'timestamp': '20200102030405',
            'url': 'https://web.archive.org/web/20200102030405/https://example.test/paper'}}})
        page = response(b'<html><h1>Example study</h1><p>Article text.</p></html>',
                        url='https://web.archive.org/web/20200102030405id_/https://example.test/paper', kind='text/html')
        with patch.object(fetch, 'get_archive_response', return_value=available), \
             patch('curl_cffi.requests.get', return_value=page):
            value = fetch.attempt_archive_snapshot(self.args.url, str(self.out), True)
        self.assertEqual(value['snapshot_at'], '20200102030405')
        self.assertEqual(value['artifact'], 'markdown')
        self.assertEqual(value['output'], str(self.out.with_suffix('.md')))
        self.assertFalse(value['content_verified'])
        self.assertEqual(self.out.read_bytes(), self.original)

    def test_jstor_retry_is_opt_in_and_host_scoped(self):
        for url, opt_in, expected in [('https://example.test/a', True, 1),
                                      ('https://www-jstor-org.proxy.test/a#page=2', False, 1),
                                      ('https://www-jstor-org.proxy.test/a#page=2', True, 2)]:
            get = Mock(return_value=response(b'no', 403))
            with self.subTest(url=url, opt_in=opt_in), self.assertRaises(ValueError):
                auth.fetch_pdf(SimpleNamespace(request=SimpleNamespace(get=get)), url, opt_in)
            self.assertEqual(get.call_count, expected)
            if expected == 2:
                self.assertIn('?acceptTC=true&coverpage=false#page=2', get.call_args.args[0])

    def test_pdflink_no_match_fails_without_scanning_other_tab(self):
        page = SimpleNamespace(url='https://unrelated.test', eval_on_selector_all=Mock())
        with patch.object(auth, 'with_context', side_effect=lambda args, fn: fn(SimpleNamespace(pages=[page]))):
            with self.assertRaises(ValueError):
                auth.cmd_pdflink(SimpleNamespace(substr='publisher'))
        page.eval_on_selector_all.assert_not_called()

    def test_partial_cli_status_is_nonzero_and_json_is_clean(self):
        value = common.result('partial', output=self.out, complete=False, missing=[{'input_url': 'missing'}])
        with patch.object(auth, 'cmd_merge', return_value=value), contextlib.redirect_stdout(io.StringIO()) as output:
            code = auth.main(['merge', str(self.out), 'https://example.test/a', '--allow-partial', '--json', '--port', '18223'])
        self.assertEqual(code, 3)
        self.assertEqual(json.loads(output.getvalue())['status'], 'partial')

    def test_legacy_entrypoint_forwards_help(self):
        child = subprocess.run([sys.executable, str(ROOT / 'robust-web-fetch/scripts/assisted.py'), '--help'], capture_output=True, text=True)
        self.assertEqual(child.returncode, 0, child.stderr)
        self.assertIn('authenticated-fetch', child.stderr)
        self.assertIn('pdflink', child.stdout)


if __name__ == '__main__':
    unittest.main()
