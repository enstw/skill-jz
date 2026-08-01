---
name: repo-publish
description: >
  Publish a local folder to GitHub as a complete repo presence: pre-publish
  audit (secrets in history, PII, redistribution rights, license) feeding an
  explicit PUBLIC-OR-PRIVATE decision (private-first when in doubt), git init
  if needed, gh repo create + push, a README.md authored from the folder's
  real contents, the repo description, a README header banner and a 1280×640
  social-preview card rendered via the genimage primitives in fallback order
  (/genimage-img2 → /genimage-nb → /genimage-canvas; stop if all fail), and the
  social-preview upload step (GitHub has no API for it). PRE-CONDITION: `gh`
  installed and authenticated (`gh auth login`). Use when asked to "publish /
  migrate this folder (or repo) to GitHub", "create a GitHub repo for this",
  "open-source this", or "repo-publish".
user-invocable: true
---

# /repo-publish — folder → complete GitHub presence

Turns a local folder into a GitHub repo that looks intentional: audited
visibility, an honest README with a banner, a description, and a social
card. The image work is delegated to the renderer primitives in a fixed
fallback chain (`/genimage-img2` → `/genimage-nb` → `/genimage-canvas` — same
`IMAGE_OK`/`IMAGE_FAIL` contract); this skill owns the workflow and the
publishing judgment.

```
audit → visibility decision → git state → README → gh create+push
      → description/topics → banner + social card → upload → verify
```

## Pre-flight

```bash
command -v gh >/dev/null || echo "GH_MISSING"
gh auth status >/dev/null 2>&1 || echo "GH_AUTH_MISSING"
```

1. `GH_MISSING` → stop: "install GitHub CLI (`brew install gh`)."
1. `GH_AUTH_MISSING` → stop: "run `gh auth login` first."
1. Each genimage primitive gates itself (its own pre-flight); a failed
   pre-flight just advances the fallback chain in Step 5 — probe there,
   not before the audit.

## Step 1: The visibility decision (public or private)

Everything hangs on this — decide **before the first push**, not after.
Run the audit; don't assume.

### Audit checklist

1. **Secrets — in the working tree AND the full history.** A key deleted in
   a later commit is still published. Prefer `gitleaks detect` when
   available; otherwise at minimum:
   ```bash
   git log -p | grep -inE "api[_-]?key|secret|token|passw(or)?d|BEGIN (RSA|OPENSSH|EC) PRIVATE" | head
   ls -la .env* *.pem id_* credentials*.json 2>/dev/null
   ```
   Any hit → either stay private, or rewrite history (`git filter-repo`, or
   start a fresh orphan branch for the public copy) **and rotate the
   credential anyway** — once pushed public, treat it as leaked.
1. **PII / personal context.** Names, rosters, graded coursework, contact
   exports, `PERSONAL-*.md`, 個資. Homework and thesis repos are the classic
   trap: the work may be shareable while the metadata is not.
1. **Redistribution rights.** Third-party fonts (a bundled CJK font is
   usually NOT redistributable — check its license before publishing it),
   paper PDFs under `refs/`, images/media you didn't make. No right to
   redistribute → strip it, or stay private.
1. **License.** Public with no LICENSE file = viewable but all-rights-
   reserved; fine for "source-visible", wrong for "please reuse". If reuse
   is intended, add one (MIT/Apache-2.0 for code; CC-BY-4.0 for docs) and
   name it in the README.
1. **Infra leakage.** Internal hostnames, absolute machine paths, VPN/infra
   hints in configs or docs.

### Decision rule

1. Audit fully clean + user explicitly wants it public → **public**.
1. Anything unresolved, or the user didn't say → **private-first**:
   `--private` now, review the rendered repo on github.com, flip later with
   `gh repo edit --visibility public` (newer gh also requires
   `--accept-visibility-change-consequences`). Flipping private→public is
   cheap; unpublishing is not — public→private later still means the content
   must be treated as having been seen (clones, mirrors, caches).
1. Record the decision and the *why* in your report.

Visibility scopes the later steps: a **social card only matters for a
public repo** (it renders on shares/embeds). For a private repo, skip Step
5's card (or generate and stage it for the future flip) — the README banner
is still worth it, collaborators see it.

## Step 2: Git state

1. Not a repo yet → `git init -b main`.
1. **`.gitignore` before the first commit** — untracked junk becomes
   permanent history at `git add .`: build outputs, `node_modules/`,
   `.env*`, OS droppings, agent-local state (`.claude/`, `.antigravitycli/`
   etc. per the project's conventions).
1. Commit any dirty work with a real message. Nothing uncommitted should be
   silently swept into a "publish" commit.

## Step 3: README.md

Author from the folder's **real contents**, not boilerplate — read the
entry points first. Structure:

1. Banner slot (filled in Step 5): `![<name>](.github/banner.png)`
1. One-line pitch — written once, reused verbatim as the repo description.
1. What it is / why it exists (a paragraph, honest scope).
1. Install / usage — commands that actually work from a fresh clone.
1. Layout — only if the tree isn't self-evident.
1. License line (matching the Step 1 decision).

Match the content's language (Traditional Chinese project → 繁體中文 README).
If the repo already has a good README, update it — don't regenerate.

## Step 4: Create, push, describe

```bash
gh repo create <name> --private|--public --source=. --remote=origin --push
gh repo edit --description "<the one-line pitch>"        # ≤ ~120 chars reads best
gh repo edit --add-topic <topic1> --add-topic <topic2>   # 3–6 topics aid discovery
```

Existing remote already on GitHub → skip create; this becomes a
"presence refresh" (description, README, images only).

## Step 5: Banner + social card (renderer primitives)

Both images live in **`.github/`** (GitHub renders relative paths from the
README, and the folder keeps the root clean):

| Artifact | Spec | Embed / use |
| :--- | :--- | :--- |
| `.github/banner.png` | wide strip, ~1600×400 | `![<name>](.github/banner.png)` at the top of README |
| `.github/social-preview.png` | **1280×640 (2:1), < 1 MB** (GitHub min 640×320) | uploaded in Step 6; shown on shares/embeds |

Renderer selection is a **fixed fallback chain**, not a per-image judgment
call. For each artifact, try in this order and move to the next only on
`IMAGE_FAIL` (or a failed pre-flight):

1. **/genimage-img2** (gpt-image-2 via Codex CLI) — first choice.
1. **/genimage-nb** (nano banana via agy CLI) — second.
1. **/genimage-canvas** (HTML/CSS composition, rasterized) — last resort;
   also the one that renders **exact text** reliably, so when it's the
   fallback that lands, lean on typography (repo name + tagline; CJK and
   house fonts: see the font guidance in /genimage-canvas § Step 2).
1. **All three failed → STOP.** Report each primitive's `IMAGE_FAIL` reason
   and halt the workflow here — no placeholder images, no silently
   continuing to Step 6. The repo is already pushed (Step 4), so nothing is
   lost; images can be retried once a renderer is fixed.

Prompting notes regardless of renderer:

1. For the AI renderers (img2, nb), keep in-image text minimal — they
   garble small type.
1. Keep ONE aesthetic across banner and card (same philosophy / same
   leading prompt sentence) so the repo reads as one identity — and reuse
   the same renderer for both artifacts once one succeeds; don't restart
   the chain per image.

Commit the images (and banner reference) — they are part of the repo.

## Step 6: Social preview upload (the no-API step)

**GitHub has no API or gh command for the social preview image.** Two paths:

1. **Manual (default):** point the user at
   `https://github.com/<owner>/<repo>/settings` → *Social preview* →
   *Upload an image*, file at `.github/social-preview.png`. Say it in the
   report as the one remaining manual step.
1. **Browser automation (only if asked):** drive the settings page with a
   connected-browser skill, if one is available in the running environment,
   using the user's logged-in session.

Verification once uploaded: `curl -s https://github.com/<owner>/<repo> |
grep -o 'og:image[^>]*'` should show a `repository-images.githubusercontent.com`
URL (the card cache can lag a few minutes).

## Step 7: Verify and report

1. `gh repo view <owner>/<repo>` — description present, visibility as
   decided.
1. Open the repo page (or capture it with the browser-cdp skill):
   README renders, banner shows, no accidental files.
1. Report: URL, **visibility + the audit reasoning behind it**, artifacts
   created, which genimage renderer landed (and any fallbacks hit along the
   chain), and what remains manual (social-preview upload, license choice
   if deferred, the flip-to-public checklist if private-first).

## Important rules

1. **Never push public without the Step 1 audit** — and when the user says
   "public" but the audit finds a hit, surface it and wait; don't publish
   over an unresolved finding.
1. The pitch line is written once and reused (README ↔ description ↔ card
   tagline) — divergence reads as neglect.
1. Don't invent content for the README — document what exists; gaps are
   listed as gaps.
