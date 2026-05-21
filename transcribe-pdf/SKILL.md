---
name: transcribe-pdf
description: Transcribe a PDF to Markdown for downstream AI reading (citation-locator verification, research notes, building a reference corpus). Use when the user asks to transcribe, convert, or extract a PDF, drops a PDF into a workspace directory and asks for .md, or starts a research session that will re-read the same PDFs multiple times. Encodes WHY: re-reading a PDF during writing costs roughly 1.5k-3k text tokens PLUS image tokens per page per lookup, while transcribed Markdown bypasses the vision pipeline entirely. Prefer the offline tool (pdf2md.py) for clean text-layer PDFs; escalate to vision-based parallel-subagent fan-out only when the text layer is unrecoverable.
allowed-tools:
  - Read
  - Write
  - Bash
  - Task
---

# transcribe-pdf — PDF → Markdown for downstream AI reading

## The cost case

Re-reading a PDF during a writing session is expensive: every
vision-based PDF read costs **~1,500–3,000 text tokens *plus* image
tokens per page** for vision processing. A thesis or research
project that revisits a single source ten times pays that cost ten
times.

A one-time Markdown transcription pays once and lets every subsequent
lookup hit a plain-text file — no vision tokens, no image
preprocessing. For projects with more than a couple of source
revisits, transcription is the cheaper option by a wide margin.

This skill's job is to make transcription the default, and to spend
vision tokens only when the source genuinely needs them.

## Decision tree

Two paths, taken in order:

- **Path A — offline tool (`pdf2md.py`).** Default for any PDF with a
  text layer (born-digital papers, most journal PDFs, OCR'd scans
  that already include text). Cheap, fast, no vision tokens. Output
  is quality-checked with a small vision sample *after* transcription
  so we still catch silent failures.
- **Path B — vision fan-out.** Only when Path A fails its quality
  check, or when `pdf2md.py` isn't installed and the work is a
  one-off where installing is overkill. Burns image tokens, but
  parallel subagent fan-out keeps wall-clock low and parent-context
  consumption at zero.

The PDF always ends up at `workspace/<pdf-stem>.md` regardless of
which path produced it.

## Path A — offline tool

1. **Locate `pdf2md.py`** (see "Locating / installing pdf2md.py"
   below). If it can't be found and isn't worth installing for this
   task, jump to Path B.

2. **Run it.** Default invocation:

   ```sh
   pdf2md.py workspace/<pdf>.pdf workspace/<name>.md
   ```

   Pass `--langs zh-Hant,en-US` (or similar BCP-47 codes) for
   non-default languages. Pass `--offset N` only if the auto-detected
   printed-page offset is wrong; otherwise let the tool detect it.
   `--force-ocr` bypasses the text-layer tiers entirely (rarely
   needed — the tool falls back to OCR automatically on pages whose
   text layer is gibberish).

   Don't `pip install` the dependencies and don't invoke with
   `python pdf2md.py`. The script is a PEP 723 single-file program;
   its shebang runs it under `uv run --script` and resolves deps in
   a throwaway environment on first run.

3. **Quality check (3-page vision sample).** Spawn **one** subagent
   with full tool access (in Claude Code, the `general-purpose`
   subagent type; use the equivalent in your runtime) with this
   brief:

   - Pick three physical pages: first content page (skip covers /
     blank versos), middle page, last content page.
   - Open those three pages in the source PDF using the subagent's
     native PDF / vision tool. Read the corresponding page spans in
     `workspace/<name>.md`.
   - Return one of:
     - `PASS` — a downstream AI can recover the printed text from
       the `.md` (minor whitespace / ligature noise OK, tables as
       fences OK, punctuation variance OK).
     - `FAIL: <reason>` — broken structure (missing pages, page
       markers misaligned), systematic OCR garble, or key content
       (footnotes, tables, quote marks) unreadable.
   - **Return only the verdict and reason to the parent.**
     Transcribed content must not enter parent context.

   The subagent **must not** write its own script (PyPDF2,
   pdfplumber, etc.) to extract text for the check. Use native
   vision; that is the whole point of the check.

4. **On PASS:** stop. The `.md` is ready for use.

5. **On FAIL:** delete `workspace/<name>.md` and run Path B.

## Path B — vision fan-out

Used when Path A fails the quality check, or as the direct path when
`pdf2md.py` isn't available. Produces the same
`workspace/<name>.md` shape so downstream consumers don't care which
path ran.

"Subagent" in this section means whatever your runtime calls a
full-tool-access subagent (Claude Code: the `general-purpose` type).

1. **Fan out in parallel, 3 pages per subagent.**
   - Spawn `⌈pages / 3⌉` subagents **concurrently in a single
     tool-call batch**. Each subagent owns one contiguous 3-page
     range (the last range may be 1–3 pages).
   - Per-page save points + 3-page batched reads is the sweet spot:
     a 31-page Chinese journal article finished in ~1.6 min on this
     setup, vs. ~10.6 min for per-20-page single-subagent and
     ~16.5 min for per-page single-subagent. Don't switch shapes
     without re-benchmarking.

2. **Each subagent does:**
   - Read all 3 pages of its range using its native vision-capable
     PDF tool (one call, batched).
   - Transcribe to Markdown preserving:
     - Headings and subheadings.
     - Paragraphs (one blank line between).
     - Footnotes inline as `¹ ...` / `² ...`, keeping the
       superscript reference in the body text.
     - Block quotes (`> ...`).
     - Lists (ordered or unordered, matching the original).
     - Tables (GFM pipe-table syntax).
     - Inline emphasis (`*italic*`, `**bold**`) where visible.
     - Romanized proper names and English inline terms exactly as
       printed.
   - Write **three separate files**, one per page, to
     `workspace/<name>/pNNNN.md` with **4-digit zero-padded** page
     numbers (e.g. `p0001.md`, `p0275.md`). Lexical sort = numeric
     order, which matters for the concatenation step.
   - Per-page writes preserve save-points — a subagent that dies
     mid-range still leaves completed pages on disk.
   - Return only a minimal status line to the parent, e.g.
     `done: physical 4-6, 3 files, 0 illegible, p0278-p0280`.
     Transcribed content must not enter parent context.

3. **Page markers.** At the start of each page, emit:

   ```
   **[Page N start]**
   ```

   `N` is the **printed** page number from the page's header or
   footer — *not* the physical PDF index. Journal reprints often
   start at something like 275, not 1. If a page has no printed
   number (title page, blank verso, figure-only page, cover),
   continue the previous page's numbering with `+1` and annotate the
   inference:

   ```
   **[Page 276 start]** <!-- inferred, no printed number -->
   ```

   Roman-numeral front matter (i, ii, iii, …) stays as printed.

4. **Concatenate.** After all subagents finish:

   ```sh
   # If you have the helper from the pdf2md repo:
   ./scripts/combine-workspace-pages.sh "<name>"
   ```

   Otherwise inline-equivalent (zero-padding makes lexical = numeric):

   ```sh
   ( first=1
     for f in workspace/<name>/p*.md; do
       [ $first -eq 0 ] && echo
       cat "$f"
       first=0
     done
   ) > workspace/<name>.md
   rm -r workspace/<name>
   ```

## Common output contract

Whichever path produced the file:

- Single file at `workspace/<pdf-stem>.md`.
- `**[Page N start]**` markers using printed page numbers, monotonic
  except at known front-matter → body transitions.
- First and last visible printed page numbers in the `.md` match
  what the PDF shows.
- Footnote numbers preserved with their text captured nearby.

After either path, spot-check those three properties before declaring
done.

## Edge cases

- **Paywalled or inaccessible source.** Record metadata (title,
  author, year, abstract) in the `.md` and stop. Do **not** fabricate
  content.
- **Scanned PDF with illegible spans.** Transcribe what's legible.
  Mark unreadable spans with `*[WARNING: illegible span on page N.]*`
  and continue. Do not guess.
- **Mixed-language document.** Transcribe in the original language(s)
  exactly as printed. Do not translate.
- **Non-PDF source** (DOCX, HTML, EPUB). Fetch the fulltext through
  the appropriate tool and save to `workspace/<name>.md` preserving
  paragraph structure. Page markers don't apply unless the source
  has them.

## Idempotence and bulk transcription

If `workspace/<name>.md` already exists and is non-empty, **skip**
that PDF — re-transcribing wastes tokens and risks regressing a file
the user has been editing.

For bulk runs, one task per PDF. Title each task with the path taken
so review is easy:
- `Transcribe <name> (pdf2md)`
- `Transcribe <name> (vision)`

## Locating / installing pdf2md.py

Run once per session, only when Path A is about to start.

### Locate the script

1. `command -v pdf2md.py` — if it returns a path, use it. Done.
2. Otherwise, search known locations in order; first match wins:
   - `$PDF2MD_HOME/pdf2md.py` (env-var override)
   - `~/homework/pdf2md/pdf2md.py`
   - `~/projects/pdf2md/pdf2md.py`
   - `~/src/pdf2md/pdf2md.py`
   - `~/code/pdf2md/pdf2md.py`
   - `~/Developer/pdf2md/pdf2md.py`
3. Last-resort filesystem probe:
   ```sh
   find ~ -maxdepth 5 -name pdf2md.py -type f \
        -not -path '*/.*' 2>/dev/null | head -n 1
   ```
4. **If found off-PATH:** symlink it to a PATH directory so future
   sessions skip steps 2–3. Prefer `~/.local/bin` (XDG default, on
   PATH for most macOS + Linux setups). Fall back to `~/bin` if
   that's already on PATH instead:
   ```sh
   mkdir -p ~/.local/bin
   ln -sf "<found-path>" ~/.local/bin/pdf2md.py
   ```
   If neither directory is on PATH, print a one-line PATH-update
   hint and proceed using the absolute path for this session.
5. **If still not found:** tell the user the canonical source is the
   `pdf2md` repo (MIT, single PEP 723 file — clone wherever your
   development tree lives) and **fall through to Path B**. The skill
   stays useful without the cheap path; only the token-economy
   advantage is missed.

### Check prerequisites (OS-detected hints)

Before invoking `pdf2md.py`, verify its prerequisites. Detect OS once:

```sh
os="$(uname -s)"   # Darwin = macOS, Linux = Linux
```

**`uv` (required on both OSes).** The script's shebang runs it under
`uv run --script`. If `command -v uv` is empty, **print** the
appropriate install hint and stop — do not auto-run package
managers, especially anything needing `sudo`:

- macOS: `brew install uv`  (or `curl -LsSf https://astral.sh/uv/install.sh | sh` if Homebrew isn't installed)
- Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`  (works on Ubuntu, Debian, Fedora, Arch, etc.)

**`tesseract` (Linux only, for OCR on scanned pages).** On macOS,
`pdf2md.py` uses Apple Vision and needs no extra binary. On Linux,
OCR runs through `ocrmypdf` + `tesseract`. If `os = Linux` and
`command -v tesseract` is empty, print:

- Ubuntu/Debian: `sudo apt install tesseract-ocr tesseract-ocr-chi-tra tesseract-ocr-eng`
- Fedora: `sudo dnf install tesseract tesseract-langpack-chi_tra tesseract-langpack-eng`
- Arch/Manjaro: `sudo pacman -S tesseract tesseract-data-chi_tra tesseract-data-eng`

Substitute language packs to match the user's `--langs`. Note:
`tesseract` is only needed when a PDF lacks a text layer; clean
born-digital PDFs go through `pdf2md.py` without touching OCR.

### Portability notes

- Every command in this section is POSIX (`uname`, `command -v`,
  `find`, `ln -s`, `mkdir -p`, `[ ... ]`) and behaves identically on
  macOS and Linux.
- `find -maxdepth` is supported on both BSD find (macOS) and GNU
  find (Linux).
- The runtime backend split (Apple Vision on macOS, `ocrmypdf` on
  Linux) is handled *inside* `pdf2md.py` — this skill doesn't need
  an OS branch beyond the install hints above.
- Do not run package-manager commands automatically (`brew`, `apt`,
  `dnf`, `pacman`). Print the hint, let the user decide.

## Further reading

The pdf2md repo is the source of truth. When numbers, defaults, or
protocol shape change there, update this skill from those files:

- `README.md` — extraction tiers, CLI flags, smart-offset detection.
- `workspace-transcription-protocol.md` — full per-PDF procedure,
  quality-check rubric, vision fan-out details, edge cases.
- `workspace-transcription-benchmark.md` — decision record behind
  the 3p × parallel fan-out default.

This skill intentionally **does not** document tier internals,
gibberish-detection thresholds, or `pdf2md.py`'s `use_ocr=False`
invariant. Those are concerns for someone editing the tool, covered
in the pdf2md repo's `AGENTS.md`. This skill consumes the output,
not the implementation.
