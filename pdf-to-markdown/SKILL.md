---
name: pdf-to-markdown
description: >
  Convert any PDF to Markdown — born-digital, scanned, or mixed. Use whenever
  a task needs text out of a PDF: extract text or tables, convert to Markdown,
  OCR a scanned document, read/summarize/quote/cite a paper or book, or build
  a transcript for repeated AI lookup. Do not hand-roll pymupdf, pdfplumber,
  or pdftotext scripts — the bundled offline converter is already a hardened
  pymupdf pipeline (per-page pymupdf4llm → raw text → OCR fallback) with
  broken-text-layer detection, CJK support, and printed-page markers, and it
  runs as one uv command with zero setup. Use vision-based transcription only
  when the offline converter fails quality checks.
---

# pdf-to-markdown

## When to Use

Reach for this skill whenever the real deliverable depends on PDF text:
extraction, Markdown conversion, OCR, translation prep, summarizing or
quoting with page-accurate citations, or building a reference transcript
for repeated lookup.

The one exception: a quick glance at one or two pages of a short PDF to
answer a throwaway question. Native PDF reading is fine for that and needs
no transcript.

## Use the Bundled Converter, Not Ad-Hoc Scripts

When a task needs PDF text, the reflex is to write a quick pymupdf /
pdfplumber / pdftotext snippet. Don't — `scripts/pdf2md.py` is already a
hardened pymupdf pipeline, and running it is the same one command of
effort:

- Per-page tier fallback: pymupdf4llm structured Markdown → raw
  `page.get_text()` → OCR (Apple Vision on macOS, ocrmypdf/tesseract
  elsewhere). Each page gets the best tier that passes checks.
- Gibberish detection that catches broken or mojibake text layers an
  ad-hoc script would silently pass through as "extracted successfully".
- CJK-aware extraction and OCR language selection (default
  `zh-Hant,en-US`, configurable via `--langs`).
- Printed-page-label detection with auto offset, emitting stable page
  markers for citation.

An ad-hoc script handles only the born-digital happy case and fails
silently on the rest.

## Why a Transcript

Repeated vision reads of a PDF are expensive: each lookup re-renders pages
and spends image-processing tokens again. A one-time Markdown transcription
lets later citation checks and claim lookups use plain text.

This skill's job is to produce one Markdown file per PDF, with stable page
markers, and to spend vision effort only when the bundled offline path
cannot produce usable text.

## Bundled Files

Resolve these paths relative to this `SKILL.md`, not relative to the user's
project:

- `scripts/pdf2md.py` - self-contained PEP 723 converter run by `uv`.
- `scripts/combine-pages.sh` - combines per-page fallback files.
- `LICENSE.pdf2md` - MIT license for the bundled converter.

Do not assume any copy of `pdf2md.py` exists in the user's home directory or on
`PATH`.

## Output Contract

Choose the output path first:

- Research/corpus workflows, or a project that already has a `workspace/`
  directory: `workspace/<pdf-stem>.md`.
- One-off extraction or conversion: `<pdf-stem>.md` next to the source PDF,
  or wherever the user asked.

The rest of this document writes `workspace/<pdf-stem>.md`; substitute the
chosen path throughout.

Whichever path produces the transcript:

- Write one file at `workspace/<pdf-stem>.md`.
- Preserve original language; do not translate.
- Preserve headings, paragraphs, lists, block quotes, tables, visible emphasis,
  romanized names, and footnote numbers where readable.
- Include page-boundary markers using printed page labels where possible.
  The bundled converter emits markers like:
  - `**[Page 1 start]**`
  - `**[Page 1 end, Page 2 start]**`
  - `**[Page 2 end]**`
- If a vision fallback page has no printed number, infer from the previous page
  and annotate it: `**[Page 276 start]** <!-- inferred, no printed number -->`.
- Mark unreadable spans as `*[WARNING: illegible span on page N.]*`; never
  guess.

If `workspace/<pdf-stem>.md` already exists and is non-empty, skip it unless the
user explicitly asks to regenerate it.

## Prerequisites

Before using `scripts/pdf2md.py`, check the platform and dependencies:

```sh
uname -s
command -v uv
```

If `uv` is missing, stop and give the user the relevant install hint. Do not run
package managers automatically.

- macOS with Homebrew: `brew install uv`
- Ubuntu/Debian: `curl -LsSf https://astral.sh/uv/install.sh | sh`

OCR prerequisites:

- macOS: the converter uses Apple Vision. No tesseract setup is needed. For
  Traditional Chinese OCR, macOS 13+ is recommended.
- Ubuntu/Debian: clean text-layer PDFs need only `uv`; scanned/OCR fallback also
  needs system OCR tools:
  `sudo apt install tesseract-ocr tesseract-ocr-chi-tra tesseract-ocr-eng ghostscript qpdf`

Substitute tesseract language packs when using non-default `--langs` values.

## Path A - Bundled Offline Converter

Use this first for born-digital PDFs, OCR'd PDFs with a text layer, and most
journal articles.

Run from the user's project root:

```sh
<path-to-skill>/scripts/pdf2md.py workspace/<pdf>.pdf workspace/<pdf-stem>.md
```

Useful flags:

- `--langs zh-Hant,en-US` - comma-separated BCP-47 codes; default is
  `zh-Hant,en-US`. This affects OCR language selection and text-gibberish
  detection.
- `--offset N` - explicit printed-page offset. Omit it by default; the converter
  auto-detects header/footer offsets and logs the decision to stderr.
- `--force-ocr` - ignore text layers and OCR every page. Use only when normal
  extraction is systematically wrong.
- `--debug` - stream per-page tier decisions to stderr; useful after a failed
  quality check.
- `--no-page-markers` - suppress page markers. Avoid this for citation work.

Do not install Python dependencies manually and do not create a virtualenv. The
script's shebang runs `uv run --script` and resolves inline PEP 723
dependencies. If a platform has trouble with the shebang, use the equivalent:

```sh
uv run --script <path-to-skill>/scripts/pdf2md.py workspace/<pdf>.pdf workspace/<pdf-stem>.md
```

## Quality Check

After Path A, visually compare a small sample against the source PDF:

1. Pick three physical pages: first content page, middle content page, last
   content page. Skip covers and blank versos.
2. Use the runtime's native PDF/vision capability to inspect those pages. Do not
   write a second text-extraction script for the check.
3. Read only the corresponding spans in `workspace/<pdf-stem>.md`.
4. Decide:
   - `PASS` - a downstream AI can recover the printed text and page labels
     despite minor whitespace, ligature, punctuation, or table-format noise.
   - `FAIL: <reason>` - missing pages, misaligned markers, systematic OCR
     garble, or unreadable key content such as footnotes, tables, or quotes.

If the runtime supports isolated workers, delegate the check so the transcribed
content does not enter the main context. If it does not, keep the check brief
and do not paste transcript content into the final response.

On `PASS`, stop. On `FAIL`, remove the bad `workspace/<pdf-stem>.md` and use
Path B.

## Path B - Vision Fallback

Use this only when Path A fails or when the PDF has no recoverable text layer.
The fallback must still produce `workspace/<pdf-stem>.md`.

Preferred shape when the runtime supports parallel workers:

1. Split the PDF into contiguous 3-page ranges.
2. Run ranges concurrently. Each worker reads its assigned pages with native
   vision/PDF capability and writes one file per page:
   `workspace/<pdf-stem>/pNNNN.md`.
3. Use 4-digit zero-padding so lexical sort equals page order.
4. Return only status lines from workers, not transcribed page content.

If parallel workers are unavailable, process the same 3-page ranges
sequentially and write the same `pNNNN.md` files.

Each page file should start with a page marker:

```md
**[Page N start]**
```

Use the printed page number from the header/footer, not the physical PDF index.
Roman-numeral front matter stays roman. If no printed number is visible, infer
from the previous page and annotate the inference.

Combine after all page files are written:

```sh
<path-to-skill>/scripts/combine-pages.sh "<pdf-stem>" [output-dir]
```

The helper expects `<output-dir>/<pdf-stem>/p*.md` (default output-dir:
`workspace`), writes `<output-dir>/<pdf-stem>.md`, and removes the per-page
directory. If the helper is unavailable, concatenate sorted `p*.md` files with
a blank line between pages and then remove the per-page directory.

## Edge Cases

- Paywalled or inaccessible source: write available metadata only (title,
  author, year, abstract/source note) and state that full text was inaccessible.
  Do not fabricate content.
- Mixed-language documents: transcribe in the original language(s).
- Non-PDF source: fetch or convert through the appropriate native tool and save
  `workspace/<name>.md`; page markers apply only when the source has page
  labels.
- Bulk transcription: one task per source. Skip existing non-empty `.md` files.

## Final Check

Before declaring done:

- First and last visible page labels in the Markdown match the PDF.
- Page markers are monotonic except at known front-matter/body transitions.
- Footnote numbers and nearby footnote text are preserved where readable.
- The final answer reports the output path and whether Path A or Path B was
  used.
