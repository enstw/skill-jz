"""Validation, atomic output, and the result contract shared by fetch skills."""
import io
import json
import os
import re
import tempfile
import subprocess
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path


def run_captured(command, timeout):
    """Stop the owned process group on deadline, including browser descendants."""
    import signal
    child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, start_new_session=True)
    try:
        stdout, stderr = child.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        for sig, wait in ((signal.SIGTERM, 5), (signal.SIGKILL, 5)):
            try:
                os.killpg(child.pid, sig)
            except ProcessLookupError:
                pass
            try:
                child.communicate(timeout=wait)
                break
            except subprocess.TimeoutExpired:
                continue
        raise TimeoutError(f'Command exceeded {timeout} seconds')
    if child.returncode:
        raise RuntimeError(stderr.strip() or f'Command exited {child.returncode}')
    return stdout


def resolve_skill(name, caller):
    override = os.environ.get(name.upper().replace('-', '_') + '_SKILL')
    roots = [Path(caller).absolute().parents[2], Path(caller).resolve().parents[2]]
    candidates = [Path(override).expanduser()] if override else [root / name for root in roots]
    for candidate in candidates:
        if (candidate / 'SKILL.md').is_file():
            return candidate
    raise RuntimeError(f'{name} skill missing; install it alongside this skill or set '
                       f'{name.upper().replace("-", "_")}_SKILL to its directory')


def atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f'.{path.name}.', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def pdf_pages(content):
    from pypdf import PdfReader
    if b'%PDF-' not in content[:1024]:
        raise ValueError('Response is not a PDF')
    try:
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted and not reader.decrypt(''):
            raise ValueError('PDF requires a password')
        count = len(reader.pages)
        if not count:
            raise ValueError('PDF contains no pages')
        # Materialize every page so a broken page tree cannot pass on header alone.
        for page in reader.pages:
            _ = page.mediabox
        return count
    except Exception as error:
        raise ValueError(f'Invalid or unreadable PDF: {error}') from error


class PageText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.heading = 0
        self.in_title = 0
        self.headings = []
        self.text = []
        self.password = False
        self.article = False

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'template', 'noscript'):
            self.hidden += 1
        if tag in ('title', 'h1'):
            self.heading += 1
        if tag == 'title':
            self.in_title += 1
        if tag == 'article':
            self.article = True
        if tag == 'input' and dict(attrs).get('type', '').lower() == 'password':
            self.password = True

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'template', 'noscript'):
            self.hidden = max(0, self.hidden - 1)
        if tag in ('title', 'h1'):
            self.heading = max(0, self.heading - 1)
        if tag == 'title':
            self.in_title = max(0, self.in_title - 1)

    def handle_data(self, data):
        if not self.hidden and data.strip():
            if not self.in_title:
                self.text.append(data.strip())
            if self.heading:
                self.headings.append(data.strip())


def validate_html(html):
    page = PageText()
    page.feed(html)
    text = ' '.join(page.text)
    if not text:
        raise ValueError('Empty page or JavaScript loading shell')
    # Match page headings, not arbitrary article prose discussing bot checks.
    gate = re.compile(r'^(just a moment|access denied|attention required|'
                      r'verify (you are|that you)|checking your browser|'
                      r'sign in|log in|login|authentication required|'
                      r'subscription required|get access|登入|登錄|存取遭拒)(\b|[\s….!：:]|$)', re.I)
    if any(gate.search(heading.strip()) for heading in page.headings):
        raise ValueError('Login, subscription, or challenge page')
    if page.password and not page.article:
        raise ValueError('Login form instead of document')
    if text.lower().strip(' .…') in ('loading', 'please wait', '載入中'):
        raise ValueError('Loading shell instead of document')
    return text


def prepare_document(content, output, content_type=''):
    suffix = Path(output).suffix.lower()
    if suffix == '.pdf':
        return content, 'native_pdf', {'pdf_pages': pdf_pages(content), 'validation': 'pdf_structure'}
    if not content.strip():
        raise ValueError('Empty response')
    is_html = 'html' in content_type.lower() or bool(re.search(
        rb'<(?:!doctype\s+html|html|head|body|form)\b', content[:4096], re.I))
    if is_html:
        html = content.decode('utf-8', errors='replace')
        validate_html(html)
        if suffix in ('.md', '.txt'):
            from markdownify import markdownify
            content = markdownify(html).encode('utf-8')
            return content, 'markdown', {'validation': 'page_screening'}
        return content, 'html', {'validation': 'page_screening'}
    return content, 'text' if suffix in ('.md', '.txt') else 'binary', {'validation': 'nonempty'}


def result(status, *, input_url=None, output=None, method=None, artifact=None,
           final_url=None, snapshot_at=None, complete=False, **extra):
    return dict(schema_version=1, status=status, input_url=input_url,
                output=str(Path(output).absolute()) if output else None,
                method=method, artifact=artifact, final_url=final_url,
                snapshot_at=snapshot_at, complete=complete,
                content_verified=False,
                fetched_at=datetime.now(timezone.utc).isoformat(), **extra)


def emit(value, as_json=False):
    if as_json:
        print(json.dumps(value, ensure_ascii=False))
    else:
        print(f'{value["status"]}: {value.get("output") or value.get("error") or value.get("method") or ""}')
        if value.get('missing'):
            print(f'Missing chapters: {len(value["missing"])}')
        if value.get('error') and value.get('output'):
            print(value['error'])
