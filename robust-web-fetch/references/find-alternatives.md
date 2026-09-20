## Not this URL — *any* copy? (books & papers)

This skill fetches the bytes of a **URL you already have**. A *different* problem is "I need document D and its canonical source is paywalled/CAPTCHA-walled" — there you want an **alternative copy**, not a harder fetch of the same URL. Highest-yield routes, in order:

1. **Above-board first** — an Unpaywall / open-access copy, an author or preprint version (SSRN, arXiv, institutional repository), or the reader's **library EZproxy / interlibrary loan**. For journal articles an OA copy often already exists.
1. **Shadow-library aggregators** (for personal/academic access to material you are citing) — start at **Anna's Archive** (`annas-archive.*`), the stable meta-index that routes to whatever Library Genesis / Z-Library mirror is currently alive; for a journal article its **scimag / Sci-Hub-by-DOI** path is usually fastest. Treat specific mirror domains as **volatile** — they rotate, die, and get typosquatted, so locate the current working host rather than trusting a hardcoded one, and verify what you download (PDF magic bytes + page count) before trusting it.
1. **dokumen.pub** sometimes surfaces a book in search, but its `/download/` endpoint is a Cloudflare **interactive CAPTCHA** → needs Tier 5, or just prefer a libgen mirror (usually faster).

> Reference mechanic that worked on `libgen.li` (2026-07; these UIs change): `index.php?req=<ISBN|DOI|title>` → pick the best file (born-digital PDF > scan > EPUB) → `ads.php?md5=<md5>` exposes a `get.php?md5=…&key=…` link → download with that referer → verify. EPUB-only? Convert with `ebooklib` + `markdownify` in spine order (chapter-level citation; no print pages).
