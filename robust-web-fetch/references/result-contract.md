# Fetch result contract (version 1)

Both fetch CLIs emit one JSON object with `--json`; diagnostics go to stderr.
Callers consume the reported `output`, because a permitted Markdown fallback
changes the requested `.pdf` path to `.md`.

| Field | Meaning |
|---|---|
| `schema_version` | `1` |
| `status` | `success`, `failed`, or `partial` |
| `input_url` | Requested source URL; null for operations on multiple URLs |
| `output` | Actual absolute artifact path; null when no artifact was written |
| `method` | `curl-cffi`, `wayback`, `camoufox`, `browser-cdp`, `authenticated`, or `authenticated-merge`; session commands use their command name |
| `artifact` | `native_pdf`, `rendered_pdf`, `markdown`, `html`, `text`, or `binary`; null for session operations and failures |
| `final_url` | Response URL after redirects; archive retrieval records the archive URL |
| `snapshot_at` | Wayback timestamp, or null |
| `fetched_at` | UTC result timestamp |
| `complete` | All requested transport items were retrieved; **not** an assertion that they comprise the full work |
| `content_verified` | Always false; the caller must audit source identity and claim support |
| `validation` | Checks performed, such as `pdf_structure` or `page_screening` |
| `pdf_pages`, `bytes` | Artifact size when applicable |
| `attempts` | Ordered automated strategies and their failures or success |
| `chapters`, `missing` | Ordered retrieved chapters with final URLs/page counts, and missing chapter URLs/errors |
| `error` | Human-readable failure explanation |

Exit 0: accepted complete transport result. Exit 1: retrieval/validation failure.
Exit 3: partial merge explicitly allowed; the output exists but is incomplete.
Argument errors use exit 2. No success state means source support was verified.

Do not commit authenticated session information or signed URLs from results
without inspecting them: final URLs may carry access parameters. In an academic
queue, retain the stable source URL and acquisition facts needed to reproduce
or audit the artifact.
